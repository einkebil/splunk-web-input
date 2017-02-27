# coding=utf-8
import unittest
import sys
import os
import time
import shutil
import re
import tempfile
import unicodedata
import lxml.html
from StringIO import StringIO

sys.path.append( os.path.join("..", "src", "bin") )
sys.path.append( os.path.join("..", "src", "bin", "website_input_app") )

from web_input import URLField, DurationField, SelectorField, WebInput
from modular_input import Field, FieldValidationException
from unit_test_web_server import UnitTestWithWebServer, skipIfNoServer

class TestURLField(unittest.TestCase):
    
    def test_url_field_valid(self):
        url_field = URLField( "test_url_field_valid", "title", "this is a test" )
        
        self.assertEqual( url_field.to_python("http://google.com").geturl(), "http://google.com" )
        self.assertEqual( url_field.to_python("http://google.com/with/path").geturl(), "http://google.com/with/path" )
        self.assertEqual( url_field.to_python("http://google.com:8080/with/port").geturl(), "http://google.com:8080/with/port" )
        
    def test_url_field_invalid(self):
        url_field = URLField( "test_url_field_invalid", "title", "this is a test" )
        
        self.assertRaises( FieldValidationException, lambda: url_field.to_python("hxxp://google.com") )
        self.assertRaises( FieldValidationException, lambda: url_field.to_python("http://") )
        self.assertRaises( FieldValidationException, lambda: url_field.to_python("google.com") )
    
class TestDurationField(unittest.TestCase):
    
    def test_duration_valid(self):
        duration_field = DurationField( "test_duration_valid", "title", "this is a test" )
        
        self.assertEqual( duration_field.to_python("1m"), 60 )
        self.assertEqual( duration_field.to_python("5m"), 300 )
        self.assertEqual( duration_field.to_python("5 minute"), 300 )
        self.assertEqual( duration_field.to_python("5"), 5 )
        self.assertEqual( duration_field.to_python("5h"), 18000 )
        self.assertEqual( duration_field.to_python("2d"), 172800 )
        self.assertEqual( duration_field.to_python("2w"), 86400 * 7 * 2 )
        
    def test_url_field_invalid(self):
        duration_field = DurationField( "test_url_field_invalid", "title", "this is a test" )
        
        self.assertRaises( FieldValidationException, lambda: duration_field.to_python("1 treefrog") )
        self.assertRaises( FieldValidationException, lambda: duration_field.to_python("minute") )   
    
class TestWebInput(UnitTestWithWebServer):
    
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp( prefix="TestWebInput" )
        #os.makedirs(self.tmp_dir)
        
    def tearDown(self):
        shutil.rmtree( self.tmp_dir )
    
    def get_test_dir(self):
        return os.path.dirname(os.path.abspath(__file__))
    
    def test_get_file_path(self):
        self.assertEquals( WebInput.get_file_path( "/Users/lmurphey/Applications/splunk/var/lib/splunk/modinputs/web_input", "web_input://TextCritical.com"), os.path.join("/Users/lmurphey/Applications/splunk/var/lib/splunk/modinputs/web_input", "2c70b6c76574eb4d825bfb194a460558.json"))
        
    def test_input_timeout(self):
        url_field = URLField( "test_input_timeout", "title", "this is a test" )
        selector_field = SelectorField( "test_web_input_css", "title", "this is a test" )
        results = WebInput.scrape_page( url_field.to_python("https://192.168.30.23/"), selector_field.to_python("div"), timeout=3 )
        result = results[0]
        self.assertEquals(result['timed_out'], True)
        
    def test_save_checkpoint(self):
        
        web_input = WebInput(timeout=3)
        
        web_input.save_checkpoint_data(self.tmp_dir, "web_input://TextCritical.com", { 'last_run': 100 })
        self.assertEquals( WebInput.last_ran(self.tmp_dir, "web_input://TextCritical.com"), 100)
        
    def test_is_expired(self):
        self.assertFalse( WebInput.is_expired(time.time(), 30) )
        self.assertTrue( WebInput.is_expired(time.time() - 31, 30) )
    
    def test_needs_another_run(self):
        
        # Test case where file does not exist
        self.assertTrue( WebInput.needs_another_run( "/Users/lmurphey/Applications/splunk/var/lib/splunk/modinputs/web_input", "web_input://DoesNotExist", 60 ) )
        
        # Test an interval right at the earlier edge
        self.assertFalse( WebInput.needs_another_run( os.path.join( self.get_test_dir(), "configs" ), "web_input://TextCritical.com", 60, 1365486765 ) )
        
        # Test an interval at the later edge
        self.assertFalse( WebInput.needs_another_run( os.path.join( self.get_test_dir(), "configs" ), "web_input://TextCritical.com", 10, 1365486775 ) )
        
        # Test interval beyond later edge
        self.assertTrue( WebInput.needs_another_run( os.path.join( self.get_test_dir(), "configs" ), "web_input://TextCritical.com", 10, 1365486776 ) )
    
    def test_scrape_page(self):
        url_field = URLField( "test_web_input", "title", "this is a test" )
        selector_field = SelectorField( "test_web_input_css", "title", "this is a test" )
        results = WebInput.scrape_page( url_field.to_python("http://textcritical.net/"), selector_field.to_python(".hero-unit.main_background") )
        result = results[0]
        self.assertEqual(result['response_code'], 200)
        self.assertEqual(len(result['match']), 1)
        
    def test_scrape_page_child_text(self):
        # This text ensure that text from nodes under the selected nodes is properly extracted
        url_field = URLField( "test_web_input", "title", "this is a test" )
        selector_field = SelectorField( "test_web_input_css", "title", "this is a test" )
        results = WebInput.scrape_page( url_field.to_python("http://textcritical.net/"), selector_field.to_python(".hero-unit.main_background"), output_matches_as_mv=True )
        result = results[0]
        self.assertEqual(result['response_code'], 200)
        self.assertEqual(len(result['match']), 1)
        
        self.assertEqual(result['match'][0], "Ancient Greek, Modern Design TextCritical.net is a website that provides a library of ancient Greek works")
        
    def test_scrape_page_mv(self):
        web_input = WebInput(timeout=3)
        
        url_field = URLField( "test_web_input", "title", "this is a test" )
        selector_field = SelectorField( "test_web_input_css", "title", "this is a test" )
        results = WebInput.scrape_page( url_field.to_python("http://textcritical.net/"), selector_field.to_python("h2"), output_matches_as_mv=True )
        result = results[0]
        self.assertEqual(result['response_code'], 200)
        self.assertEqual(len(result['match']), 3)
        
        out = StringIO()
        web_input.output_event(result, stanza="web_input://textcritical_net", index="main", source="test_web_input", sourcetype="sourcetype", out=out)
        self.assertEquals( len(re.findall("match=", out.getvalue())), 3)
        
    def test_scrape_unavailable_page(self):
        url_field = URLField( "test_web_input", "title", "this is a test" )
        selector_field = SelectorField( "test_web_input_css", "title", "this is a test" )
        results = WebInput.scrape_page( url_field.to_python("http://192.168.30.23/"), selector_field.to_python(".hero-unit.main_background"), timeout=3 )
        result = results[0]
        self.assertEqual(result['timed_out'], True)
        
    @skipIfNoServer
    def test_scrape_page_with_credentials(self):
        url_field = URLField( "test_web_input", "title", "this is a test" )
        selector_field = SelectorField( "test_web_input_css", "title", "this is a test" )
        results = WebInput.scrape_page( url_field.to_python("http://127.0.0.1:" + str(self.web_server_port)), selector_field.to_python("tr"), username="admin", password="changeme", timeout=3, output_matches_as_mv=True )
        result = results[0]
        #print result['match']
        self.assertEqual(len(result['match']), 30)
        
    @skipIfNoServer
    def test_scrape_page_with_invalid_credentials(self):
        url_field = URLField( "test_web_input", "title", "this is a test" )
        selector_field = SelectorField( "test_web_input_css", "title", "this is a test" )
        results = WebInput.scrape_page( url_field.to_python("http://127.0.0.1:" + str(self.web_server_port)), selector_field.to_python("tr"), timeout=3, output_matches_as_mv=True )
        result = results[0]
        #print result['match']
        self.assertEqual(len(result['match']), 0)

    @skipIfNoServer
    def test_scrape_page_with_case_insensitive_selector(self):
        # https://lukemurphey.net/issues/1739
        url_field = URLField( "test_web_input", "title", "this is a test" )
        selector_field = SelectorField( "test_web_input_css", "title", "this is a test" )
        results = WebInput.scrape_page( url_field.to_python("http://127.0.0.1:" + str(self.web_server_port) + "/html"), selector_field.to_python("H1"), timeout=3, output_matches_as_mv=True )
        result = results[0]
        #print result['match']
        self.assertEqual(len(result['match']), 1)
    
    def test_unparsable(self):
        url_field = URLField( "test_web_input", "title", "this is a test" )
        selector_field = SelectorField( "test_web_input_css", "title", "this is a test" )
        results = WebInput.scrape_page( url_field.to_python("http://textcritical.net/media/images/link_external.png"), selector_field.to_python(".hero-unit .main_background"), timeout=3, output_matches_as_mv=True )
        result = results[0]
        self.assertEqual(result['match'], [])
        
    def test_scrape_encoding_detect_page(self):
        url_field = URLField( "test_web_input", "title", "this is a test" )
        selector_field = SelectorField( "test_web_input_css", "title", "this is a test" )
        results = WebInput.scrape_page( url_field.to_python("http://textcritical.net/work/new-testament/Mark/1/2?async"), selector_field.to_python(".verse-container") )
        result = results[0]
        self.assertEqual(result['response_code'], 200)
        self.assertEqual(len(result['match']), 45)
        #print result['match']
        self.assertEqual(unicodedata.normalize('NFC', result['match'][1]), unicodedata.normalize('NFC', u"2 Καθὼς γέγραπται ἐν τῷ Ἠσαίᾳ τῷ προφήτῃ Ἰδοὺ ἀποστέλλω τὸν ἄγγελόν μου πρὸ προσώπου σου , ὃς κατασκευάσει τὴν ὁδόν σου :"))
        self.assertEqual(result['encoding'], "utf-8")
                
    def test_scrape_encoding_detect_sniff(self):
        url_field = URLField( "test_web_input", "title", "this is a test" )
        selector_field = SelectorField( "test_web_input_css", "title", "this is a test" )
        results = WebInput.scrape_page( url_field.to_python("http://textcritical.net/work/new-testament/Mark/1/2?async"), selector_field.to_python(".verse-container"), charset_detect_meta_enabled=False, charset_detect_content_type_header_enabled=False, charset_detect_sniff_enabled=True )
        result = results[0]
        
        self.assertEqual(result['response_code'], 200)
        self.assertEqual(len(result['match']), 45)
        self.assertEqual(result['encoding'], "utf-8")
        
    def test_scrape_encoding_detect_meta(self):
        url_field = URLField( "test_web_input", "title", "this is a test" )
        selector_field = SelectorField( "test_web_input_css", "title", "this is a test" )
        results = WebInput.scrape_page( url_field.to_python("http://textcritical.net/work/new-testament/Mark/1/2"), selector_field.to_python(".verse-container"), charset_detect_meta_enabled=True, charset_detect_content_type_header_enabled=False, charset_detect_sniff_enabled=False )
        result = results[0]
        
        self.assertEqual(result['response_code'], 200)
        self.assertEqual(result['encoding'], "utf-8")
    
    def test_scrape_encoding_detect_content_type_header(self):
        url_field = URLField( "test_web_input", "title", "this is a test" )
        selector_field = SelectorField( "test_web_input_css", "title", "this is a test" )
        results = WebInput.scrape_page( url_field.to_python("http://textcritical.net/work/new-testament/Mark/1/2?async"), selector_field.to_python(".verse-container"), charset_detect_meta_enabled=False, charset_detect_content_type_header_enabled=True, charset_detect_sniff_enabled=False )
        result = results[0]
        
        self.assertEqual(result['response_code'], 200)
        self.assertEqual(len(result['match']), 45)
        self.assertEqual(result['encoding'], "utf-8")
    
    def test_scrape_page_adjacent_selector(self):
        # For bug: http://lukemurphey.net/issues/773
        
        url_field = URLField( "test_web_input", "title", "this is a test" )
        selector_field = SelectorField( "test_web_input_css", "title", "this is a test" )
        results = WebInput.scrape_page( url_field.to_python("http://textcritical.net/"), selector_field.to_python("h1+p,.sharing-buttons"), timeout=3, output_matches_as_mv=True )
        result = results[0]
        
        self.assertEqual(len(result['match']), 2)
    
    @skipIfNoServer
    def test_scrape_page_name_attributes(self):
        url_field = URLField( "test_web_input", "title", "this is a test" )
        selector_field = SelectorField( "test_web_input_css", "title", "this is a test" )
        results = WebInput.scrape_page( url_field.to_python("http://127.0.0.1:" + str(self.web_server_port)), selector_field.to_python(".hd"), username="admin", password="changeme", timeout=3, name_attributes=["class"] )
        result = results[0]
        
        self.assertEqual(len(result['hd']), 31)
        
    @skipIfNoServer
    def test_scrape_page_name_attributes_separate_fields(self):
        url_field = URLField( "test_web_input", "title", "this is a test" )
        selector_field = SelectorField( "test_web_input_css", "title", "this is a test" )
        results = WebInput.scrape_page( url_field.to_python("http://127.0.0.1:" + str(self.web_server_port)), selector_field.to_python(".hd"), username="admin", password="changeme", timeout=3, name_attributes=["class"], output_matches_as_separate_fields=True, output_matches_as_mv=False)
        result = results[0]
        
        self.assertEqual(result['match_hd_1'], 'Mode:')
    
    @skipIfNoServer
    def test_scrape_page_name_attributes_escaped_name(self):
        url_field = URLField( "test_web_input", "title", "this is a test" )
        selector_field = SelectorField( "test_web_input_css", "title", "this is a test" )
        results = WebInput.scrape_page( url_field.to_python("http://127.0.0.1:" + str(self.web_server_port)), selector_field.to_python("input"), username="admin", password="changeme", timeout=3, name_attributes=["onclick"], include_empty_matches=True)
        result = results[0]
        
        self.assertTrue('btnBerTest__' in result)
        self.assertTrue('btnReset__' in result)
        
    def test_field_escaping(self):
        self.assertTrue(WebInput.escape_field_name("tree()"), "tree__")
        
    def test_field_escaping_whitespace(self):
        self.assertTrue(WebInput.escape_field_name("  "), "blank")
        
    def test_field_escaping_reserved(self):
        self.assertTrue(WebInput.escape_field_name("source"), "match_source")
        self.assertTrue(WebInput.escape_field_name("host"), "match_host")
        self.assertTrue(WebInput.escape_field_name("sourcetype"), "match_sourcetype")
        self.assertTrue(WebInput.escape_field_name("_time"), "match_time")
    
    def test_scrape_page_bad_encoding(self):
        #http://lukemurphey.net/issues/987
        
        url_field = URLField( "test_web_input", "title", "this is a test" )
        selector_field = SelectorField( "test_web_input_css", "title", "this is a test" )
        results = WebInput.scrape_page( url_field.to_python("http://rss.slashdot.org/Slashdot/slashdot"), selector_field.to_python("description") )
        result = results[0]
        
        self.assertEqual(result['response_code'], 200)
        self.assertGreater(len(result['match']), 0)
        self.assertEqual(result['encoding'], "ISO-8859-1")
        
    @skipIfNoServer
    def test_scape_page_custom_user_agent(self):
        url_field = URLField( "test_web_input", "title", "this is a test" )
        selector_field = SelectorField( "test_web_input_css", "title", "this is a test" )
        results = WebInput.scrape_page( url_field.to_python("http://127.0.0.1:" + str(self.web_server_port) + "/header_reflection"), selector_field.to_python(".user-agent"), timeout=3, output_matches_as_mv=True, user_agent="test_scape_page_custom_user_agent")
        result = results[0]
        
        #print result['match']
        self.assertEqual(len(result['match']), 1)
        self.assertEqual(result['match'][0], "test_scape_page_custom_user_agent")
        
    @skipIfNoServer
    def test_scape_page_xml(self):
        # http://lukemurphey.net/issues/1144
        url_field = URLField( "test_web_input", "title", "this is a test" )
        selector_field = SelectorField( "test_web_input_css", "title", "this is a test" )
        results = WebInput.scrape_page( url_field.to_python("http://127.0.0.1:" + str(self.web_server_port) + "/xml"), selector_field.to_python("COOK_TEMP"), timeout=3, output_matches_as_mv=True)
        result = results[0]
        
        self.assertEqual(len(result['match']), 1)
        self.assertEqual(result['match'][0], "695")
    
    @skipIfNoServer
    def test_scape_page_names_as_tag_name(self):
        # http://lukemurphey.net/issues/1145
        url_field = URLField( "test_web_input", "title", "this is a test" )
        selector_field = SelectorField( "test_web_input_css", "title", "this is a test" )
        results = WebInput.scrape_page( url_field.to_python("http://127.0.0.1:" + str(self.web_server_port) + "/xml"), selector_field.to_python("COOK_TEMP"), timeout=3, output_matches_as_mv=True, use_element_name=True)
        result = results[0]
        
        self.assertEqual(len(result['match']), 1)
        self.assertEqual(result['match'][0], "695")
        self.assertEqual(len(result['cook_temp']), 1)
        self.assertEqual(result['cook_temp'][0], "695")
        
    @skipIfNoServer
    def test_scape_page_match_prefix(self):
        
        url_field = URLField( "test_web_input", "title", "this is a test" )
        selector_field = SelectorField( "test_web_input_css", "title", "this is a test" )
        results = WebInput.scrape_page( url_field.to_python("http://127.0.0.1:" + str(self.web_server_port) + "/xml"), selector_field.to_python("COOK_TEMP"), timeout=3, output_matches_as_mv=True, use_element_name=True, match_prefix="prefix_")
        result = results[0]
        
        self.assertEqual(len(result['prefix_cook_temp']), 1)
        self.assertEqual(result['prefix_cook_temp'][0], "695")
        
    @skipIfNoServer
    def test_scape_page_match_prefix_with_multiple(self):
        # http://lukemurphey.net/issues/1628
        
        url_field = URLField( "test_web_input", "title", "this is a test" )
        selector_field = SelectorField( "test_web_input_css", "title", "this is a test" )
        results = WebInput.scrape_page( url_field.to_python("http://127.0.0.1:" + str(self.web_server_port) + "/xml"), selector_field.to_python("MISC > *"), timeout=3, output_matches_as_mv=True, use_element_name=True, match_prefix="prefix_")
        result = results[0]
        
        self.assertEqual(len(result['prefix_string']), 3)
        self.assertEqual(result['prefix_string'][0], "ABC")
        self.assertEqual(result['prefix_string'][1], "DEF")
        self.assertEqual(result['prefix_string'][2], "GHI")
        
    def test_add_auth_to_url(self):
        self.assertEqual(WebInput.add_auth_to_url("http://tree.com", "admin", "changeme"), "http://admin:changeme@tree.com")
        self.assertEqual(WebInput.add_auth_to_url("http://tree.com:8888", "admin", "changeme"), "http://admin:changeme@tree.com:8888")
        
    def test_add_auth_to_url_existing_user_pass(self):
        self.assertEqual(WebInput.add_auth_to_url("http://user:abc1234@tree.com", "admin", "changeme"), "http://admin:changeme@tree.com")
        
    def test_add_auth_to_url_no_username(self):
        self.assertEqual(WebInput.add_auth_to_url("http://tree.com", None, "changeme"), "http://tree.com")
        self.assertEqual(WebInput.add_auth_to_url("http://tree.com", "", "changeme"), "http://tree.com")
        
    def test_add_auth_to_url_no_password(self):
        self.assertEqual(WebInput.add_auth_to_url("http://tree.com", "admin", None), "http://tree.com")
        self.assertEqual(WebInput.add_auth_to_url("http://tree.com", "admin", ""), "http://tree.com")
        
class TestWebInputCrawling(unittest.TestCase):
    """
    http://lukemurphey.net/issues/762
    """
        
    def test_cleanup_link(self):
        
        self.assertEqual(WebInput.cleanup_link("http://textcritical.net/read#something", "http://textcritical.net/"), "http://textcritical.net/read")
        self.assertEqual(WebInput.cleanup_link("read/", "http://textcritical.net/"), "http://textcritical.net/read/")
        self.assertEqual(WebInput.cleanup_link("../read/", "http://textcritical.net/test/"), "http://textcritical.net/read/")
        self.assertEqual(WebInput.cleanup_link("read#test", "http://textcritical.net/"), "http://textcritical.net/read")
        self.assertEqual(WebInput.cleanup_link("read/", "http://textcritical.net/test/"), "http://textcritical.net/test/read/")
        
    def test_remove_anchor(self):
        
        self.assertEqual(WebInput.remove_anchor("http://textcritical.net/read#something"), "http://textcritical.net/read")
        self.assertEqual(WebInput.remove_anchor("http://textcritical.net/read/"), "http://textcritical.net/read/")
        
    def test_extract_links(self):
        
        tree = lxml.html.fromstring("""
        <!DOCTYPE html>
        <html>
        <body>
        
        <h1>Test</h1>
        
        <a>Test link[1]</a>
        <a href="http://textcritical.net">Test link[2]</a>
        <a href="link_3">Test link[3]</a>
        <a href="../link_4">Test link[4]</a>
        <a href="../link_4">Test duplicate link[4]</a>
        <a href="link_3#test">Test duplicate anchor link[3]</a>
        </body>
        </html>
        """)
        
        links = WebInput.extract_links(tree, "http://textcritical.net/read/")
        
        self.assertEqual(len(links), 3)
        
        self.assertEqual(links[0], "http://textcritical.net")
        self.assertEqual(links[1], "http://textcritical.net/read/link_3")
        self.assertEqual(links[2], "http://textcritical.net/link_4")
        
    def test_extract_links_filter(self):
        
        tree = lxml.html.fromstring("""
        <!DOCTYPE html>
        <html>
        <body>
        
        <h1>Test</h1>
        
        <a>Test link[1]</a>
        <a href="http://textcritical.net">Test link[2]</a>
        <a href="link_3">Test link[3]</a>
        <a href="http://textcritical.com">Test link[3]</a>
        </body>
        </html>
        """)
        
        links = WebInput.extract_links(tree, "http://textcritical.net/read/", url_filter="http://textcritical.net")
        
        self.assertEqual(len(links), 2)
        
        self.assertEqual(links[0], "http://textcritical.net")
        self.assertEqual(links[1], "http://textcritical.net/read/link_3")
        
    def test_scape_page_spider(self):
        # http://lukemurphey.net/issues/762
        
        url_field = URLField( "test_web_input", "title", "this is a test" )
        selector_field = SelectorField( "test_web_input_css", "title", "this is a test" )
        results = WebInput.scrape_page( url_field.to_python("http://textcritical.net"), selector_field.to_python(".footer-links > li > a"), timeout=3, output_matches_as_mv=True, page_limit=5)
        result = results[0]
        
        self.assertEqual(len(results), 5)
        self.assertEqual(len(result['match']), 3)
        self.assertEqual(result['match'][0], "Source code")
        
    def test_is_url_in_url_filter(self):
        self.assertTrue(WebInput.is_url_in_url_filter("http://textcritical.net/tree", "http://textcritical.net*"))
        self.assertTrue(WebInput.is_url_in_url_filter("http://textcritical.net/tree", "http://textcritical.net/*"))
        self.assertFalse(WebInput.is_url_in_url_filter("http://textcritical.net/", "http://textcritical.com/*"))
        self.assertTrue(WebInput.is_url_in_url_filter("http://textcritical.com", "http://textcritical.*"))
    
    def test_scape_page_spider_depth_limit(self):
        # http://lukemurphey.net/issues/1312

        url_field = URLField( "test_web_input", "title", "this is a test" )
        selector_field = SelectorField( "test_web_input_css", "title", "this is a test" )
        results = WebInput.scrape_page( url_field.to_python("http://textcritical.net"), selector_field.to_python(".footer-links > li > a"), timeout=3, output_matches_as_mv=True, page_limit=5, depth_limit=0)
        self.assertEqual(len(results), 1)
        
    def test_scape_page_spider_from_non_matching_links(self):
        # http://lukemurphey.net/issues/1366

        url_field = URLField( "test_web_input", "title", "this is a test" )
        selector_field = SelectorField( "test_web_input_css", "title", "this is a test" )
        results = WebInput.scrape_page( url_field.to_python("http://textcritical.net"), selector_field.to_python(".ajah-loading"), timeout=3, output_matches_as_mv=True, page_limit=5, depth_limit=3)
        
        self.assertGreater(len(results), 1) # This should return only one result if link extraction only applies to matched pages 
        
class TestRawContent(UnitTestWithWebServer):
    """
    http://lukemurphey.net/issues/1168
    """
    
    @skipIfNoServer
    def test_get_raw_content(self):
        url_field = URLField( "test_web_input", "title", "this is a test" )
        selector_field = SelectorField( "test_get_raw_content", "title", "this is a test" )
        results = WebInput.scrape_page( url_field.to_python("http://127.0.0.1:" + str(self.web_server_port) + "/xml"), selector_field.to_python("COOK_TEMP"), timeout=3, output_matches_as_mv=True, include_raw_content=True)
        result = results[0]
        
        self.assertEqual(len(results), 1)
        self.assertEqual(result['content'][0:15], "<nutcallstatus>")
        
    @skipIfNoServer
    def test_get_raw_content_empty_selector(self):
        url_field = URLField( "test_web_input", "title", "this is a test" )
        selector_field = SelectorField( "test_get_raw_content_empty_selector", "title", "this is a test" )
        results = WebInput.scrape_page( url_field.to_python("http://127.0.0.1:" + str(self.web_server_port) + "/xml"), selector_field.to_python(""), timeout=3, output_matches_as_mv=True, include_raw_content=True)
        result = results[0]
        
        self.assertEqual(len(results), 1)
        self.assertEqual(result['content'][0:15], "<nutcallstatus>")
        
class TestCustomSeparator(UnitTestWithWebServer):
    """
    See http://lukemurphey.net/issues/763
    """
    
    @skipIfNoServer
    def test_custom_separator(self):
        url_field = URLField( "test_web_input", "title", "this is a test" )
        selector_field = SelectorField( "test_custom_separator", "title", "this is a test" )
        results = WebInput.scrape_page( url_field.to_python("http://127.0.0.1:" + str(self.web_server_port) + "/xml"), selector_field.to_python("FOOD1"), timeout=3, output_matches_as_mv=True, text_separator=":")
        result = results[0]
        
        self.assertEqual(len(results), 1)
        self.assertEqual(result['match'][0], "Food1:OPEN:1800:4")
        
    def test_append_if_not_empty_both_have_values(self):
        self.assertEqual(WebInput.append_if_not_empty("tree", "frog", ":"), "tree:frog")
        
    def test_append_if_first_has_value(self):
        self.assertEqual(WebInput.append_if_not_empty("tree", "", ":"), "tree")
        
    def test_append_if_second_has_value(self):
        self.assertEqual(WebInput.append_if_not_empty("", "frog", ":"), "frog")
        
    def test_append_if_neither_has_value(self):
        self.assertEqual(WebInput.append_if_not_empty("", "", ":"), "")
    
class TestBrowserRendering(UnitTestWithWebServer):
    """
    http://lukemurphey.net/issues/1323
    """
    
    BROWSER = None
    
    @skipIfNoServer
    def test_scrape_page(self):
        url_field = URLField( "test_web_input", "title", "this is a test" )
        selector_field = SelectorField( "test_custom_separator", "title", "this is a test" )
        results = WebInput.scrape_page( url_field.to_python("http://127.0.0.1:" + str(self.web_server_port) + "/html"), selector_field.to_python("h1"), timeout=3, output_matches_as_mv=True, browser=self.BROWSER)
        result = results[0]
        
        self.assertEqual(len(results), 1)
        self.assertEqual(result['match'][0], "Heading")
        self.assertEqual(result['browser'], self.BROWSER)
    
    @skipIfNoServer
    def test_get_result(self):
        
        # Don't execute this for the integrated client
        if self.BROWSER == WebInput.INTEGRATED_CLIENT:
            return
        
        url_field = URLField( "test_web_input", "title", "this is a test" )
        
        content = WebInput.get_result_browser(url_field.to_python("http://127.0.0.1:" + str(self.web_server_port) + "/html"), browser=self.BROWSER, sleep_seconds=2)
        
        self.assertEqual(content[0:5], '<html')
        
    @skipIfNoServer
    def test_get_result_basic_auth(self):
        
        # Don't execute this for the integrated client
        if self.BROWSER == WebInput.INTEGRATED_CLIENT:
            return
        
        url_field = URLField( "test_web_input", "title", "this is a test" )
        
        content = WebInput.get_result_browser(url_field.to_python("http://admin:changeme@127.0.0.1:" + str(self.web_server_port) + "/"), browser=self.BROWSER, sleep_seconds=2)
        
        self.assertGreaterEqual(content.find("Basic YWRtaW46Y2hhbmdlbWU=authenticated!"), 0)
    
    @skipIfNoServer
    def test_get_result_basic_auth_as_args(self):
        
        # Don't execute this for the integrated client
        if self.BROWSER == WebInput.INTEGRATED_CLIENT:
            return
        
        url_field = URLField( "test_web_input", "title", "this is a test" )
        
        content = WebInput.get_result_browser(url_field.to_python("http://127.0.0.1:" + str(self.web_server_port) + "/"), browser=self.BROWSER, sleep_seconds=2, username="admin", password="changeme")
        
        self.assertGreaterEqual(content.find("Basic YWRtaW46Y2hhbmdlbWU=authenticated!"), 0)
        
class TestBrowserRenderingFirefox(TestBrowserRendering):
    BROWSER = WebInput.FIREFOX
    
class TestBrowserRenderingIntegrated(TestBrowserRendering):
    BROWSER = WebInput.INTEGRATED_CLIENT
        
if __name__ == "__main__":
    loader = unittest.TestLoader()
    suites = []
    suites.append(loader.loadTestsFromTestCase(TestWebInput))
    suites.append(loader.loadTestsFromTestCase(TestWebInputCrawling))
    suites.append(loader.loadTestsFromTestCase(TestRawContent))
    suites.append(loader.loadTestsFromTestCase(TestCustomSeparator))
    suites.append(loader.loadTestsFromTestCase(TestBrowserRenderingFirefox))
    suites.append(loader.loadTestsFromTestCase(TestBrowserRenderingIntegrated))
    
    try:
        test_runner = unittest.TextTestRunner(verbosity=2)
        result = test_runner.run(unittest.TestSuite(suites))
    
    finally:
        # Shutdown the server. Note that it should shutdown automatically since it is a daemon thread but this code will ensure it is stopped too.
        UnitTestWithWebServer.shutdownServer()
    
    sys.exit(not result.wasSuccessful())