import unittest
from unittest import TestCase


from src import iter_key_values_from_chars


class TestIterKeyValuesFromChars(TestCase):

    def test_parses_unquoted_key_value_pair(self):
        it = iter_key_values_from_chars("KEY=value")
        self.assertEqual(next(it), ("KEY", "value"))
        
        it = iter_key_values_from_chars("key=value")
        self.assertEqual(next(it), ("key", "value"))
        
        it = iter_key_values_from_chars("KEY1=value")
        self.assertEqual(next(it), ("KEY1", "value"))

        it = iter_key_values_from_chars("KEY =value")
        self.assertEqual(next(it), ("KEY", "value"))

        it = iter_key_values_from_chars("KEY= value")
        self.assertEqual(next(it), ("KEY", "value"))
        
        it = iter_key_values_from_chars("KEY = value")
        self.assertEqual(next(it), ("KEY", "value"))
        
        it = iter_key_values_from_chars("KEY\t=\t\tvalue")
        self.assertEqual(next(it), ("KEY", "value"))
        
        it = iter_key_values_from_chars(" KEY=value")
        self.assertEqual(next(it), ("KEY", "value"))
        
        it = iter_key_values_from_chars("\tKEY=value")
        self.assertEqual(next(it), ("KEY", "value"))
        
        it = iter_key_values_from_chars("\nKEY=value")
        self.assertEqual(next(it), ("KEY", "value"))
        
        it = iter_key_values_from_chars("KEY=value ")
        self.assertEqual(next(it), ("KEY", "value"))
        
        it = iter_key_values_from_chars("KEY=value\t")
        self.assertEqual(next(it), ("KEY", "value"))
        
        it = iter_key_values_from_chars("KEY=value\n")
        self.assertEqual(next(it), ("KEY", "value"))

    def test_parses_doubly_quoted_values(self):
        it = iter_key_values_from_chars('KEY="value"')
        self.assertEqual(next(it), ("KEY", "value"))
        
        it = iter_key_values_from_chars('KEY=" value"')
        self.assertEqual(next(it), ("KEY", " value"))
        
        it = iter_key_values_from_chars('KEY="value "')
        self.assertEqual(next(it), ("KEY", "value "))
        
        it = iter_key_values_from_chars('KEY= "value"')
        self.assertEqual(next(it), ("KEY", "value"))
        
        it = iter_key_values_from_chars('KEY="value" ')
        self.assertEqual(next(it), ("KEY", "value"))

        it = iter_key_values_from_chars('KEY="value with \'single-quotes\'"')
        self.assertEqual(next(it), ("KEY", "value with 'single-quotes'"))
        
        it = iter_key_values_from_chars(r'KEY="value with escaped \"double-quotes\""')
        self.assertEqual(next(it), ("KEY", 'value with escaped "double-quotes"'))
        
        it = iter_key_values_from_chars(r'KEY="value with escaped \nnewline"')
        self.assertEqual(next(it), ("KEY", "value with escaped \nnewline"))
        
        it = iter_key_values_from_chars(r'KEY="value with escaped\ttab"')
        self.assertEqual(next(it), ("KEY", "value with escaped\ttab"))
        
        it = iter_key_values_from_chars(r'KEY="value with escaped \\ backslash"')
        
        it = iter_key_values_from_chars('KEY= "value"')
        self.assertEqual(next(it), ("KEY", "value"))
        
        it = iter_key_values_from_chars('KEY="value" ')
        self.assertEqual(next(it), ("KEY", "value"))

        it = iter_key_values_from_chars('KEY="value with \'single-quotes\'"')
        self.assertEqual(next(it), ("KEY", "value with 'single-quotes'"))
        
        it = iter_key_values_from_chars(r'KEY="value with escaped \"double-quotes\""')
        self.assertEqual(next(it), ("KEY", 'value with escaped "double-quotes"'))
        
        it = iter_key_values_from_chars(r'KEY="value with escaped \nnewline"')
        self.assertEqual(next(it), ("KEY", "value with escaped \nnewline"))
        
        it = iter_key_values_from_chars(r'KEY="value with escaped\ttab"')
        self.assertEqual(next(it), ("KEY", "value with escaped\ttab"))
        
        it = iter_key_values_from_chars(r'KEY="value with escaped \\ backslash"')
        self.assertEqual(next(it), ("KEY", "value with escaped \\ backslash"))
        
        it = iter_key_values_from_chars(r'KEY="value with escaped \' single-quote"')
        self.assertEqual(next(it), ("KEY", "value with escaped ' single-quote"))
        
        it = iter_key_values_from_chars(r'KEY="value with escaped \r\nCR LF"')
        self.assertEqual(next(it), ("KEY", "value with escaped \r\nCR LF"))
        
        it = iter_key_values_from_chars(r'KEY="value with escaped \r\nCR LF"')
        self.assertEqual(next(it), ("KEY", "value with escaped \r\nCR LF"))

    def test_parses_singly_quoted_values(self):
        it = iter_key_values_from_chars("KEY='value'")
        self.assertEqual(next(it), ("KEY", "value")) 
        
        it = iter_key_values_from_chars("KEY=' value'")
        self.assertEqual(next(it), ("KEY", " value")) 
        
        it = iter_key_values_from_chars("KEY='value '")
        self.assertEqual(next(it), ("KEY", "value ")) 
        
        it = iter_key_values_from_chars("KEY= 'value'")
        self.assertEqual(next(it), ("KEY", "value")) 
        
        it = iter_key_values_from_chars("KEY='value' ")
        self.assertEqual(next(it), ("KEY", "value")) 
        
        it = iter_key_values_from_chars(r"KEY='value with escaped backslash \\'")
        self.assertEqual(next(it), ("KEY", "value with escaped backslash \\")) 
        
        it = iter_key_values_from_chars(r"KEY='value with escaped quote \''")
        self.assertEqual(next(it), ("KEY", "value with escaped quote '")) 

    def test_parses_empty_values(self):
        it = iter_key_values_from_chars("KEY=")
        self.assertEqual(next(it), ("KEY", ""))
        
        it = iter_key_values_from_chars("KEY= ")
        self.assertEqual(next(it), ("KEY", ""))
        
        it = iter_key_values_from_chars("KEY=\t")
        self.assertEqual(next(it), ("KEY", ""))
        
        it = iter_key_values_from_chars("KEY=\n")
        self.assertEqual(next(it), ("KEY", ""))
        
        it = iter_key_values_from_chars("KEY=\t\n")
        self.assertEqual(next(it), ("KEY", ""))

    def test_parses_blank_lines_and_empty_string(self):
        it = iter_key_values_from_chars("")
        self.assertEqual(len(list(it)), 0)
        
        it = iter_key_values_from_chars("\n")
        self.assertEqual(len(list(it)), 0)
        
        it = iter_key_values_from_chars("\t")
        self.assertEqual(len(list(it)), 0)
        
        it = iter_key_values_from_chars("\n".join([
            "",
            "KEY1=value1",
            "",
            "KEY2=value2",
            "\t",
            "\t\v",
            "KEY3=value3",
            "",
        ]))
        self.assertEqual(next(it), ("KEY1", "value1"))
        self.assertEqual(next(it), ("KEY2", "value2"))
        self.assertEqual(next(it), ("KEY3", "value3"))

    def test_parses_multiple_key_value_pairs(self):
        it = iter_key_values_from_chars("\n".join([
            "KEY1=value1",
            "KEY2=value2",
            'KEY3="value3"',
            "KEY4='value4'",
            "'KEY5'=value5",
        ]))
        self.assertEqual(next(it), ("KEY1", "value1"))
        self.assertEqual(next(it), ("KEY2", "value2"))
        self.assertEqual(next(it), ("KEY3", "value3"))
        self.assertEqual(next(it), ("KEY4", "value4"))
        self.assertEqual(next(it), ("KEY5", "value5"))

    def test_parses_comments(self):
        it = iter_key_values_from_chars("\n".join([
            "KEY1=value1",
            "# Comment on separate line",
            "KEY2=value2 # Comment after unquoted value",
            'KEY3="value3"# Comment after double-quoted value',
            "KEY4='value4'# Comment after single-quoted value",
            "KEY5=# Commend after empty value"
        ]))
        self.assertEqual(next(it), ("KEY1", "value1"))
        self.assertEqual(next(it), ("KEY2", "value2"))
        self.assertEqual(next(it), ("KEY3", "value3"))
        self.assertEqual(next(it), ("KEY4", "value4"))
        self.assertEqual(next(it), ("KEY5", ""))


if __name__ == "__main__":
    unittest.main()
