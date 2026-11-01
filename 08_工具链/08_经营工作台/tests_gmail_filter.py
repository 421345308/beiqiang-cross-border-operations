import unittest
from gmail_filter import classify_mail, buyer_intent, new_buyer_summary


class GmailFilteringTests(unittest.TestCase):
    def test_newsletter_and_promotions_are_not_client_replies(self):
        self.assertEqual(classify_mail({'from':'buyer@example.com','list-unsubscribe':'<https://example.com/unsubscribe>',
            'auto-submitted':'auto-generated'},direction='inbound',subject='Our latest offers',body='New footwear styles'),'promotion')
        self.assertEqual(classify_mail({'from':'buyer@example.com'},direction='inbound',labels=['CATEGORY_PROMOTIONS'],
            subject='Weekly sale',body='Save 30% on shoes'),'promotion')
    def test_real_reply_is_not_discarded_by_gmail_category_or_footer(self):
        headers={'from':'buyer@example.com','in-reply-to':'<our-message>','list-unsubscribe':'<https://example.com>'}
        self.assertEqual(classify_mail(headers,direction='inbound',labels=['CATEGORY_PROMOTIONS'],subject='Re: Footwear'),'conversation')
    def test_clear_new_procurement_request_is_not_lost_in_promotions(self):
        text='We are looking for a supplier of knitted shoes. Could you provide a quotation?'
        self.assertTrue(buyer_intent('Footwear enquiry',text))
        self.assertEqual(classify_mail({'from':'buyer@example.com'},direction='inbound',labels=['CATEGORY_PROMOTIONS'],
            subject='Footwear enquiry',body=text),'conversation')
    def test_vacation_and_transactional_autoresponses_are_separate(self):
        self.assertEqual(classify_mail({'from':'buyer@example.com','auto-submitted':'auto-replied','in-reply-to':'<our>'},
            direction='inbound',subject='Automatic reply: holiday'),'automatic')
        self.assertEqual(classify_mail({'from':'no-reply@example.com'},direction='inbound',subject='Your account update'),'automatic')
    def test_outbound_is_preserved_even_with_bulk_headers(self):
        self.assertEqual(classify_mail({'precedence':'bulk','list-unsubscribe':'value'},direction='outbound'),'conversation')
    def test_new_buyer_detection_requires_footwear_context(self):
        self.assertTrue(new_buyer_summary('Footwear sourcing','We are looking for a supplier of knitted shoes.'))
        self.assertFalse(new_buyer_summary('Electronics','We are looking for a supplier of cable products.'))
        self.assertFalse(new_buyer_summary('New footwear','Discover this week’s latest offers.'))
        self.assertTrue(new_buyer_summary('采购鞋子','我们需要采购鞋子并咨询报价。'))
    def test_supplier_pitch_is_not_a_new_buyer(self):
        body='I would like to introduce our company and products. We are producing shoe care products. Could you tell us if you are interested in our shoes?'
        self.assertFalse(new_buyer_summary('Shoe care manufacturer',body))
        self.assertEqual(classify_mail({'from':'seller@example.com'},direction='inbound',subject='Shoe care manufacturer',body=body),'promotion')
    def test_ticket_confirmation_does_not_inherit_intent_from_quoted_message(self):
        body="#134100647: Footwear\nSubmitted\nWe'll pick up your ticket soon\nFrom: sales@example.com\nPlease send me a quotation for shoes."
        self.assertFalse(new_buyer_summary('Re: Footwear',body))
        self.assertEqual(classify_mail({'from':'support@example.com'},direction='inbound',subject='Re: Footwear',body=body),'automatic')
    def test_real_forwarded_buyer_request_keeps_authored_text(self):
        body='Could you kindly provide pricing and available size ranges for the footwear?\nFrom: seller@example.com\nPrevious thread'
        self.assertEqual(new_buyer_summary('FW: Footwear',body),'咨询鞋类价格和尺码')
    def test_summary_identifies_the_buyers_actual_questions(self):
        body='Could you provide pricing, MOQ and available sizes for the shoes?'
        self.assertEqual(new_buyer_summary('Footwear sourcing',body),'咨询鞋类价格、起订量和尺码')
        self.assertEqual(new_buyer_summary('Footwear sourcing','Please send us a shoe catalogue and sample.'),'咨询鞋类样品和产品目录')

if __name__=='__main__':unittest.main()
