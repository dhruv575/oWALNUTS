import unittest
from pair_snapshot import words,address


class AbiTests(unittest.TestCase):
    def test_integer_precision_and_address_padding(self):
        value=2**111+123
        self.assertEqual(words('0x'+format(value,'064x'),1),[value])
        self.assertEqual(address('0x'+format(1,'064x')),'0x'+'0'*39+'1')
        with self.assertRaises(ValueError):address('0x'+format(2**160,'064x'))

    def test_wrong_word_length_and_nonhex_rejected(self):
        with self.assertRaises(ValueError):words('0x01',1)
        with self.assertRaises(ValueError):words('0x'+'g'*64,1)


if __name__=='__main__':unittest.main()
