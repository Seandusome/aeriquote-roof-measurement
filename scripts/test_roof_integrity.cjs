const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');const s=fs.readFileSync('app.py','utf8');
const code=s.split('\n').find(x=>x.startsWith('function localPolygonAreaM2('))+s.slice(s.indexOf('function outlineMatchesBuilding('),s.indexOf('function drawEdgeMeasurements('));const c={L:{latLng:p=>Array.isArray(p)?{lat:p[0],lng:p[1]}:p}};vm.createContext(c);vm.runInContext(code,c);
let roof={total_roof_sqft:1000,roof_ground_sqft:900,roof_coverage_ratio:1,segments:[{pitch_degrees:25,area_sqft:1000}]};
assert(c.reviewAutomaticRoof({...roof}).needs_remeasure,'Missing outline must block quote');
console.log('PASS: missing automatic outline cannot remain silently quotable');

const outline=[[52,-106],[52,-105.9999],[52.0001,-105.9999],[52.0001,-106]],ground=c.localPolygonAreaM2(outline.map(p=>c.L.latLng(p)))*10.76391041671,surface=ground/Math.cos(Math.PI/6),valid={outline,latitude:52,longitude:-106,roof_ground_sqft:ground,building_ground_sqft:ground,roof_coverage_ratio:1,total_roof_sqft:surface,segments:[{pitch_degrees:30,area_sqft:surface}]};
assert.equal(c.reviewAutomaticRoof({...valid}).automatic_review_warning,undefined);
for(const change of [{roof_coverage_ratio:.5},{building_ground_sqft:ground*2},{building_ground_sqft:0},{segments:[]},{segments:[{pitch_degrees:79,area_sqft:surface}]},{total_roof_sqft:1}])assert(c.reviewAutomaticRoof({...valid,...change}).automatic_review_warning);
const missing=c.reviewAutomaticRoof({...valid,outline:null});c.reviewAutomaticRoof(missing);assert.equal(missing.automatic_roof_sqft,surface,'Re-review must retain original provider area for correction');
console.log('PASS: complete roof accepted; missing coverage/sections/pitches and implausible areas blocked; repeated review preserves original automatic area');
