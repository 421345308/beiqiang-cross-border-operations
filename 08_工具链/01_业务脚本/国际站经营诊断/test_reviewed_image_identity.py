import unittest
from repair_reviewed_gallery import canonical_detail_url,remove_reviewed_detail_images
from xml.etree import ElementTree as E

class ImageIdentityTests(unittest.TestCase):
    def test_observed_exact_cdn_render_suffixes(self):
        url='https://sc04.alicdn.com/kf/H123.png'
        for suffix in ('','_350x350.jpg','_350x350.png'):
            self.assertEqual(canonical_detail_url(url.replace('https:','')+suffix,[url]),url)

    def test_no_substring_or_unobserved_alias(self):
        url='https://sc04.alicdn.com/kf/H123.png'
        for alias in (url+'_999x999.png',url+'?crop=true',url.replace('H123','H1234')):
            with self.assertRaises(AssertionError):canonical_detail_url(alias,[url])

    def test_ambiguous_duplicate_is_rejected(self):
        url='https://sc04.alicdn.com/kf/H123.png'
        with self.assertRaises(AssertionError):canonical_detail_url(url,[url,url])

    def test_exact_removal_retains_other_images_and_gallery_membership(self):
        root=E.Element('schema');details=E.SubElement(root,'field',id='detailImage');group=E.SubElement(details,'complex-values');images=E.SubElement(group,'field',id='images');gallery=E.SubElement(group,'field',id='gallery');E.SubElement(gallery,'value').text='150'
        for url in ('a','b','c','d','obsolete'):
            row=E.SubElement(images,'complex-values');field=E.SubElement(row,'field',id='imageURL');E.SubElement(field,'value').text=url
        result=remove_reviewed_detail_images(root,['a','b','c','d','obsolete'],['obsolete'])
        self.assertEqual(result,['a','b','c','d']);self.assertEqual([v.text for v in images.findall('.//value')],result);self.assertEqual(gallery.findtext('value'),'150')
        with self.assertRaises(AssertionError):remove_reviewed_detail_images(root,result,['a'])

if __name__=='__main__':unittest.main()
