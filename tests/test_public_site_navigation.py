"""Navigation may reflect authentication, but cannot create accounts or entitlements."""
import unittest
from public_site_navigation import INDUSTRIES, PAGES, industry_for, signed_in_links


class NavigationLinks(unittest.TestCase):
    def test_each_industry_uses_selected_page_not_account_default(self):
        for slug, code in PAGES.items():
            with self.subTest(slug=slug):
                source='<a href="/site/start-free-trial" aria-label="Start Free Trial"><span>Free Trial →</span></a>'
                result=signed_in_links(source,'industries/'+slug+'.html','snow')
                self.assertIn('href="/?industry='+code+'"',result)
                self.assertIn('Start measuring',result)
                self.assertNotIn('Free Trial',result)

    def test_explicit_valid_industry_query(self):
        for code in INDUSTRIES:
            result=signed_in_links('<a href="/site/trial-signup?industry='+code+'">Trial</a>','index.html','roofing')
            self.assertIn('/?industry='+code,result)

    def test_external_or_unrelated_links_untouched(self):
        for href in ['https://other.invalid/site/trial-signup','//other.invalid/site/start-free-trial','/site/pricing','/site/terms-of-use','mailto:support@aeriquote.com']:
            source='<a href="'+href+'">Original</a>'
            self.assertEqual(signed_in_links(source,'index.html','paving'),source)

    def test_untrusted_industry_cannot_become_redirect(self):
        self.assertEqual(industry_for('trial-signup.html','paving','industry=https://other.invalid'),'paving')
        self.assertEqual(industry_for('index.html','unknown','industry=%22%3Escript'),'roofing')

    def test_login_replaced_and_inner_markup_removed(self):
        result=signed_in_links("<a class='login' href='/dealer-login'>Log In</a>",'industries/paving-sealcoating.html','snow')
        self.assertIn('Open app',result)
        self.assertIn('/?industry=paving',result)
        self.assertNotIn('Log In',result)


if __name__=='__main__':unittest.main()
