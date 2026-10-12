"""SAM 3 binary masks to editable geographic drafts; no generated coordinates."""
import base64
import io
import json
import math
import os
import time
import urllib.error
import urllib.parse
import urllib.request

ENDPOINT = 'https://fal.run/fal-ai/sam-3/image'
MAX_BYTES = 8 * 1024 * 1024


def decode_mask(raw):
    import numpy as np
    from PIL import Image
    if len(raw) > MAX_BYTES:
        raise ValueError('Mask too large')
    with Image.open(io.BytesIO(raw)) as image:
        if image.format != 'PNG' or max(image.size) > 2048 or min(image.size) < 2:
            raise ValueError('Invalid mask image')
        rgba = np.asarray(image.convert('RGBA'))
    if np.any(rgba[:, :, 3] < 255):
        return (rgba[:, :, 3] > 127).astype('uint8')
    rgb = rgba[:, :, :3]
    # apply_mask=False must return a binary mask, never the coloured aerial.
    if not np.all(rgb.max(axis=2) - rgb.min(axis=2) <= 2):
        raise ValueError('Expected a binary segmentation mask')
    return (rgb[:, :, 0] > 127).astype('uint8')


def read_mask(url, timeout=5):
    if isinstance(url, str) and url.startswith('data:image/png;base64,'):
        return decode_mask(base64.b64decode(url.split(',', 1)[1], validate=True))
    parsed = urllib.parse.urlparse(url if isinstance(url, str) else '')
    host = parsed.hostname or ''
    if parsed.scheme != 'https' or not (host == 'fal.media' or host.endswith('.fal.media')) or parsed.username or parsed.password:
        raise ValueError('Invalid mask download location')
    # Do not forward the API key to media downloads or follow redirected URLs.
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args):
            return None
    opener = urllib.request.build_opener(NoRedirect)
    with opener.open(urllib.request.Request(url), timeout=timeout) as response:
        raw = response.read(MAX_BYTES + 1)
    return decode_mask(raw)


def cell_outline(component):
    """Follow actual pixel-cell edges, preserving narrow strips' area."""
    import numpy as np
    edges = {}
    padded = np.pad(component.astype(bool), 1)
    interior = padded[1:-1, 1:-1]
    for neighbours, start, end in [
        (padded[:-2, 1:-1], (0, 0), (1, 0)),
        (padded[1:-1, 2:], (1, 0), (1, 1)),
        (padded[2:, 1:-1], (1, 1), (0, 1)),
        (padded[1:-1, :-2], (0, 1), (0, 0)),
    ]:
        for y, x in zip(*np.nonzero(interior & ~neighbours)):
            a = (int(x)+start[0], int(y)+start[1])
            b = (int(x)+end[0], int(y)+end[1])
            if a in edges:
                raise ValueError('Ambiguous touching boundaries')
            edges[a] = b
    if not edges:
        raise ValueError('Empty outline')
    first = min(edges); point = first; points = []
    while point in edges:
        points.append(point); point = edges.pop(point)
    if point != first or edges:
        raise ValueError('Mask contains holes or separate boundaries')
    return points


def masks_to_suggestions(masks, lat, lng, zoom, surface):
    import cv2
    import numpy as np
    import ai_trace
    cv2.setNumThreads(1)
    polygons = []; rejected = 0; accepted = []
    for mask in masks:
        if mask.shape[0] != mask.shape[1]:
            raise ValueError('Mask aspect ratio differs from aerial')
        if mask.mean() > .9:
            rejected += 1; continue
        n, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=4)
        for label in range(1, n):
            x, y, w, h, count = stats[label]
            if count < 20:
                continue
            if x == 0 or y == 0 or x+w == mask.shape[1] or y+h == mask.shape[0]:
                rejected += 1; continue  # cropped surfaces are incomplete
            component = labels == label
            if any(a.shape == component.shape and np.count_nonzero(a & component) / max(1, np.count_nonzero(a | component)) > .85 for a in accepted):
                continue
            try:
                boundary = np.array(cell_outline(component), dtype=np.float32).reshape(-1, 1, 2)
                poly = None
                for tolerance in (.25, .5, .75, 1, 1.5, 2):
                    candidate = cv2.approxPolyDP(boundary, tolerance, True)
                    if 3 <= len(candidate) <= 40 and abs(cv2.contourArea(candidate)-count)/count <= .02:
                        # Check shape overlap as well as total area.
                        reconstructed = np.zeros((mask.shape[0]*2, mask.shape[1]*2), dtype='uint8')
                        cv2.fillPoly(reconstructed, [np.rint(candidate*2).astype('int32')], 1)
                        sampled = reconstructed[1::2, 1::2].astype(bool)
                        iou = np.count_nonzero(sampled & component)/max(1, np.count_nonzero(sampled | component))
                        if iou >= .97:
                            poly = candidate[:, 0, :]; break
                if poly is None:
                    raise ValueError('Outline cannot be simplified safely')
                height, width = mask.shape
                item = {'name': ('Lawn' if surface == 'lawn' else 'Paved surface')+' section '+str(len(polygons)+1),
                        'points': [{'x': float(px)/width, 'y': float(py)/height} for px, py in poly]}
                ai_trace.validate_polygons({'polygons': [item]}, lat, lng, zoom)
                if len(polygons) == 6:
                    rejected += 1; continue
                polygons.append(item); accepted.append(component)
            except ValueError:
                rejected += 1
    suggestions = ai_trace.validate_polygons({'polygons': polygons}, lat, lng, zoom)
    return suggestions, rejected


def suggest(image, lat, lng, zoom, surface):
    import ai_trace
    key = os.environ.get('FAL_KEY', '').strip()
    if not key:
        raise ai_trace.ProviderError('SAM 3 tracing needs FAL_KEY in the test service environment. It does not use OpenAI credits.')
    if surface not in ai_trace.SURFACES:
        raise ValueError('Choose Lawn or Paved Surface')
    body = {'image_url': ai_trace.image_preview(image), 'prompt': 'grass lawn' if surface == 'lawn' else 'paved asphalt or concrete surface',
            'apply_mask': False, 'sync_mode': True, 'output_format': 'png',
            'return_multiple_masks': True, 'max_masks': 12, 'include_scores': True}
    request = urllib.request.Request(ENDPOINT, data=json.dumps(body).encode(),
        headers={'Authorization': 'Key '+key, 'Content-Type': 'application/json', 'X-Fal-No-Retry': '1'})
    deadline = time.monotonic()+45
    try:
        with urllib.request.urlopen(request, timeout=35) as response:
            raw = response.read(32*1024*1024+1)
            if len(raw) > 32*1024*1024:
                raise ValueError('Segmentation response too large')
            data = json.loads(raw)
        entries = data.get('masks')
        if not isinstance(entries, list) or len(entries) > 12:
            raise ValueError('Invalid segmentation response')
        masks = []; low_confidence = 0
        for i, entry in enumerate(entries):
            scores = data.get('scores') or []
            metadata = data.get('metadata') or []
            score = scores[i] if i < len(scores) else metadata[i].get('score') if i < len(metadata) else None
            if score is not None and (isinstance(score, bool) or not isinstance(score, (int, float)) or not math.isfinite(score) or not 0 <= score <= 1):
                raise ValueError('Invalid segmentation score')
            if score is not None and score < .6:
                low_confidence += 1; continue
            remaining = deadline-time.monotonic()
            if remaining <= 0:
                raise TimeoutError()
            masks.append(read_mask(entry.get('url'), timeout=min(5,remaining)))
        suggestions, rejected = masks_to_suggestions(masks, lat, lng, zoom, surface)
        return suggestions, {'provider': 'fal-sam3', 'masks': len(entries), 'rejected_regions': rejected+low_confidence}
    except urllib.error.HTTPError as error:
        messages = {401: 'fal rejected FAL_KEY. Check the key in Render.',
                    402: 'fal credits are unavailable. Check fal billing.',
                    403: 'fal denied access. Check key permissions and available credits.',
                    429: 'fal request limit reached. Wait before trying again.',
                    422: 'fal rejected the SAM 3 request format.'}
        raise ai_trace.ProviderError(messages.get(error.code, 'SAM 3 service request failed (HTTP '+str(error.code)+').')) from None
    except (TimeoutError, urllib.error.URLError):
        raise ai_trace.ProviderError('SAM 3 tracing timed out or could not connect. Your saved measurements are unchanged.') from None
    except (ValueError, KeyError, TypeError, AttributeError, OSError):
        raise ai_trace.ProviderError('SAM 3 returned a mask that could not be converted safely. Use manual Area Measure for this surface.') from None
