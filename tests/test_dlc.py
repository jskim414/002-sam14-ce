import unittest
from extractors.dlc import unwrap
from extractors.lwc import FormatError

class DlcWrapperTests(unittest.TestCase):
    def test_measured_header_vectors(self):
        expected=bytes.fromhex('66000000')+b'SN14SCEXVER0001\0'
        for code,app,vector in [(32,4598950,'0206f614bb23850f7805e5c39cb0b613fdec331d'),(33,4598960,'0b5440b183f429df5db78a250d0c62a5be6213cb')]:
            decoded,method=unwrap(bytes.fromhex(vector),f'scedaexce{code}.s14',app)
            self.assertEqual(decoded,expected);self.assertEqual(method,'DLC_LCG_XOR_V1')
    def test_plain_container_is_unchanged(self):
        data=bytes(4)+b'SN14SCEXVER0001\0'+b'synthetic payload'
        self.assertEqual(unwrap(data,'scedaexce01.s14'),(data,'PLAIN'))
    def test_missing_wrong_profile_and_short_input_fail_closed(self):
        vector=bytes.fromhex('0206f614bb23850f7805e5c39cb0b613fdec331d')
        for name,app in [('scedaexce32.s14',None),('scedaexce32.s14',4598960),('unrecognized.s14',4598950),('scedaexce32.s14',True)]:
            with self.assertRaises(FormatError):unwrap(vector,name,app)
        with self.assertRaisesRegex(FormatError,'Truncated'):unwrap(vector[:8],'scedaexce32.s14',4598950)
