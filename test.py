from dataclasses import dataclass
from pathlib import Path
from typing import Literal
import unittest
from unittest import TestCase


from src import datadotenv, iter_vars_from_dotenv_chars, Var


class TestDatadotenv(TestCase):

    def test_instantiates_dataclass_with_primitive_types(self):
        
        @dataclass(frozen=True)
        class MyDotenv:
            str_var: str
            bool_var1: bool
            bool_var2: bool
            bool_var3: bool
            bool_var4: bool
            int_var: int
            float_var: float
            unset_var: None

        spec = datadotenv(MyDotenv)

        self.assertEqual(
            spec.from_str("\n".join([
                'STR_VAR="foo"',
                'BOOL_VAR1=True',
                "BOOL_VAR2='true'",
                'BOOL_VAR3="False"',
                'BOOL_VAR4=false',
                'INT_VAR=42',
                'FLOAT_VAR=3.14',
                'UNSET_VAR=',
            ])),
            MyDotenv(
                str_var="foo",
                bool_var1=True,
                bool_var2=True,
                bool_var3=False,
                bool_var4=False,
                int_var=42,
                float_var=3.14,
                unset_var=None,
            )
        )

    def test_instantiates_dataclass_with_composite_types(self):

        @dataclass(frozen=True)
        class MyDotenv:
            literal_var1: Literal["foo", 42]
            literal_var2: Literal["foo", 42]

        spec = datadotenv(MyDotenv)

        self.assertEqual(
            spec.from_str("\n".join([
                'LITERAL_VAR1="foo"',
                'LITERAL_VAR2=42',
            ])),
            MyDotenv(
                literal_var1="foo",
                literal_var2=42,
            )
        )

    def test_instantiates_dataclass_with_defaults(self):

        @dataclass(frozen=True)
        class MyDotenv:
            str_var: str = "foo"
            int_var: int = 42
            float_var: float = 3.14
            none_var: None = None
            literal_var: Literal["foo", "bar"] = "foo"
        
        spec = datadotenv(MyDotenv)

        # Test will use defaults when unset
        self.assertEqual(
            spec.from_str(""),
            MyDotenv(
                str_var="foo",
                int_var=42,
                float_var=3.14,
                none_var=None,
                literal_var="foo"
            )
        )

        # Test defaults can be overridden when set 
        self.assertEqual(
            spec.from_str("\n".join([
                "STR_VAR=bar",
                "INT_VAR=420",
                "FLOAT_VAR=2.71",
                "NONE_VAR=",
                "LITERAL_VAR=bar",
            ])),
            MyDotenv(
                str_var="bar",
                int_var=420,
                float_var=2.71,
                none_var=None,
                literal_var="bar"
            )
        )

    def test_handles_dataclasses_with_file_paths(self):
        
        @dataclass(frozen=True)
        class MyDotenv:
            file_path: Path

        # Test raises when non-existent by default
        with self.assertRaises(datadotenv.error.FilePathDoesNotExist):
            datadotenv(MyDotenv).from_str("\n".join([
                'FILE_PATH=./non-existent'
            ]))

        # Test resolves path by default
        self.assertEqual(
            datadotenv(MyDotenv).from_str("\n".join([
                'FILE_PATH=./src/../src'
            ])),
            MyDotenv(Path("./src").resolve())
        )

        # Test option not not resolve 
        self.assertEqual(
            datadotenv(MyDotenv, resolve_file_paths=False).from_str("\n".join([
                'FILE_PATH=./src'
            ])),
            MyDotenv(Path("./src"))
        )

        # Test option to not check existence
        self.assertAlmostEqual(
            datadotenv(MyDotenv, file_paths_must_exist=False).from_str("\n".join([
                'FILE_PATH=./non-existent'
            ])),
            MyDotenv(file_path=Path("./non-existent").resolve())
        )

    def test_supports_different_casing_options(self):

        @dataclass(frozen=True)
        class MyDotenv:
            normal_casing: str
            mixed_CASING: str
        
        # Test defaults to uppercase
        self.assertAlmostEqual(
            datadotenv(MyDotenv).from_str("\n".join([
                'NORMAL_CASING=foo',
                'MIXED_CASING=bar',
            ])),
            MyDotenv(
                normal_casing="foo",
                mixed_CASING="bar",
            )
        )
        
        # Test explicit uppercase
        self.assertAlmostEqual(
            datadotenv(MyDotenv, case="upper").from_str("\n".join([
                'NORMAL_CASING=foo',
                'MIXED_CASING=bar',
            ])),
            MyDotenv(
                normal_casing="foo",
                mixed_CASING="bar",
            )
        )
        
        # Test lowercase
        self.assertAlmostEqual(
            datadotenv(MyDotenv, case="lower").from_str("\n".join([
                'normal_casing=foo',
                'mixed_casing=bar',
            ])),
            MyDotenv(
                normal_casing="foo",
                mixed_CASING="bar",
            )
        )
        
        # Test preserve casing
        self.assertAlmostEqual(
            datadotenv(MyDotenv, case="preserve").from_str("\n".join([
                'normal_casing=foo',
                'mixed_CASING=bar',
            ])),
            MyDotenv(
                normal_casing="foo",
                mixed_CASING="bar",
            )
        )

        # Test ignore casing
        self.assertAlmostEqual(
            datadotenv(MyDotenv, case="ignore").from_str("\n".join([
                'nOrMaL_cAsInG=foo',
                'MiXeD_cAsInG=bar',
            ])),
            MyDotenv(
                normal_casing="foo",
                mixed_CASING="bar",
            )
        )

    def test_supports_different_options_for_complete_or_incomplete_description_of_dotenv(self):

        @dataclass(frozen=True)
        class MyDotenv:
            var: str

        # Test default: dataclass must fully describe dotenv
        with self.assertRaises(datadotenv.error.VariableNotSpecified):
            datadotenv(MyDotenv).from_str("\n".join([
                'VAR=foo',
                'NOT_DESCRIBED_IN_DATACLASS=bar',
            ])),
            
        # Test explicit: dataclass must fully describe dotenv
        # using `allow_incomplete=False`
        with self.assertRaises(datadotenv.error.VariableNotSpecified):
            datadotenv(MyDotenv, allow_incomplete=False).from_str("\n".join([
                'VAR=foo',
                'NOT_DESCRIBED_IN_DATACLASS=bar',
            ]))

        # Test can accept incomplete dataclass with `allow_incomplete=True` 
        self.assertEqual(
            datadotenv(MyDotenv, allow_incomplete=True).from_str("\n".join([
                'VAR=foo',
                'NOT_DESCRIBED_IN_DATACLASS=bar',
            ])),
            MyDotenv(var="foo")
        )


class TestIterNameValuesFromChars(TestCase):

    def test_parses_unquoted_key_value_pair(self):
        it = iter_vars_from_dotenv_chars("KEY=value")
        self.assertEqual(next(it), Var("KEY", "value"))
        
        it = iter_vars_from_dotenv_chars("key=value")
        self.assertEqual(next(it), Var("key", "value"))
        
        it = iter_vars_from_dotenv_chars("KEY1=value")
        self.assertEqual(next(it), Var("KEY1", "value"))

        it = iter_vars_from_dotenv_chars("KEY =value")
        self.assertEqual(next(it), Var("KEY", "value"))

        it = iter_vars_from_dotenv_chars("KEY= value")
        self.assertEqual(next(it), Var("KEY", "value"))
        
        it = iter_vars_from_dotenv_chars("KEY = value")
        self.assertEqual(next(it), Var("KEY", "value"))
        
        it = iter_vars_from_dotenv_chars("KEY\t=\t\tvalue")
        self.assertEqual(next(it), Var("KEY", "value"))
        
        it = iter_vars_from_dotenv_chars(" KEY=value")
        self.assertEqual(next(it), Var("KEY", "value"))
        
        it = iter_vars_from_dotenv_chars("\tKEY=value")
        self.assertEqual(next(it), Var("KEY", "value"))
        
        it = iter_vars_from_dotenv_chars("\nKEY=value")
        self.assertEqual(next(it), Var("KEY", "value"))
        
        it = iter_vars_from_dotenv_chars("KEY=value ")
        self.assertEqual(next(it), Var("KEY", "value"))
        
        it = iter_vars_from_dotenv_chars("KEY=value\t")
        self.assertEqual(next(it), Var("KEY", "value"))
        
        it = iter_vars_from_dotenv_chars("KEY=value\n")
        self.assertEqual(next(it), Var("KEY", "value"))

    def test_parses_doubly_quoted_values(self):
        it = iter_vars_from_dotenv_chars('KEY="value"')
        self.assertEqual(next(it), Var("KEY", "value"))
        
        it = iter_vars_from_dotenv_chars('KEY=" value"')
        self.assertEqual(next(it), Var("KEY", " value"))
        
        it = iter_vars_from_dotenv_chars('KEY="value "')
        self.assertEqual(next(it), Var("KEY", "value "))
        
        it = iter_vars_from_dotenv_chars('KEY= "value"')
        self.assertEqual(next(it), Var("KEY", "value"))
        
        it = iter_vars_from_dotenv_chars('KEY="value" ')
        self.assertEqual(next(it), Var("KEY", "value"))

        it = iter_vars_from_dotenv_chars('KEY="value with \'single-quotes\'"')
        self.assertEqual(next(it), Var("KEY", "value with 'single-quotes'"))
        
        it = iter_vars_from_dotenv_chars(r'KEY="value with escaped \"double-quotes\""')
        self.assertEqual(next(it), Var("KEY", 'value with escaped "double-quotes"'))
        
        it = iter_vars_from_dotenv_chars(r'KEY="value with escaped \nnewline"')
        self.assertEqual(next(it), Var("KEY", "value with escaped \nnewline"))
        
        it = iter_vars_from_dotenv_chars(r'KEY="value with escaped\ttab"')
        self.assertEqual(next(it), Var("KEY", "value with escaped\ttab"))
        
        it = iter_vars_from_dotenv_chars(r'KEY="value with escaped \\ backslash"')
        self.assertEqual(next(it), Var("KEY", "value with escaped \\ backslash"))
        
        it = iter_vars_from_dotenv_chars('KEY= "value"')
        self.assertEqual(next(it), Var("KEY", "value"))
        
        it = iter_vars_from_dotenv_chars('KEY="value" ')
        self.assertEqual(next(it), Var("KEY", "value"))

        it = iter_vars_from_dotenv_chars('KEY="value with \'single-quotes\'"')
        self.assertEqual(next(it), Var("KEY", "value with 'single-quotes'"))
        
        it = iter_vars_from_dotenv_chars(r'KEY="value with escaped \"double-quotes\""')
        self.assertEqual(next(it), Var("KEY", 'value with escaped "double-quotes"'))
        
        it = iter_vars_from_dotenv_chars(r'KEY="value with escaped \nnewline"')
        self.assertEqual(next(it), Var("KEY", "value with escaped \nnewline"))
        
        it = iter_vars_from_dotenv_chars(r'KEY="value with escaped\ttab"')
        self.assertEqual(next(it), Var("KEY", "value with escaped\ttab"))
        
        it = iter_vars_from_dotenv_chars(r'KEY="value with escaped \\ backslash"')
        self.assertEqual(next(it), Var("KEY", "value with escaped \\ backslash"))
        
        it = iter_vars_from_dotenv_chars(r'KEY="value with escaped \' single-quote"')
        self.assertEqual(next(it), Var("KEY", "value with escaped ' single-quote"))
        
        it = iter_vars_from_dotenv_chars(r'KEY="value with escaped \r\nCR LF"')
        self.assertEqual(next(it), Var("KEY", "value with escaped \r\nCR LF"))
        
        it = iter_vars_from_dotenv_chars(r'KEY="value with escaped \r\nCR LF"')
        self.assertEqual(next(it), Var("KEY", "value with escaped \r\nCR LF"))

    def test_parses_singly_quoted_values(self):
        it = iter_vars_from_dotenv_chars("KEY='value'")
        self.assertEqual(next(it), Var("KEY", "value")) 
        
        it = iter_vars_from_dotenv_chars("KEY=' value'")
        self.assertEqual(next(it), Var("KEY", " value")) 
        
        it = iter_vars_from_dotenv_chars("KEY='value '")
        self.assertEqual(next(it), Var("KEY", "value ")) 
        
        it = iter_vars_from_dotenv_chars("KEY= 'value'")
        self.assertEqual(next(it), Var("KEY", "value")) 
        
        it = iter_vars_from_dotenv_chars("KEY='value' ")
        self.assertEqual(next(it), Var("KEY", "value")) 
        
        it = iter_vars_from_dotenv_chars(r"KEY='value with escaped backslash \\'")
        self.assertEqual(next(it), Var("KEY", "value with escaped backslash \\")) 
        
        it = iter_vars_from_dotenv_chars(r"KEY='value with escaped quote \''")
        self.assertEqual(next(it), Var("KEY", "value with escaped quote '")) 

    def test_parses_unset_values(self):
        it = iter_vars_from_dotenv_chars("KEY=")
        self.assertEqual(next(it), Var("KEY", None))
        
        it = iter_vars_from_dotenv_chars("KEY= ")
        self.assertEqual(next(it), Var("KEY", None))
        
        it = iter_vars_from_dotenv_chars("KEY=\t")
        self.assertEqual(next(it), Var("KEY", None))
        
        it = iter_vars_from_dotenv_chars("KEY=\n")
        self.assertEqual(next(it), Var("KEY", None))
        
        it = iter_vars_from_dotenv_chars("KEY=\t\n")
        self.assertEqual(next(it), Var("KEY", None))

    def test_parses_empty_strings(self):
        it = iter_vars_from_dotenv_chars('KEY=""')
        self.assertEqual(next(it), Var("KEY", ""))

    def test_parses_blank_lines_and_empty_string(self):
        it = iter_vars_from_dotenv_chars("")
        self.assertEqual(len(list(it)), 0)
        
        it = iter_vars_from_dotenv_chars("\n")
        self.assertEqual(len(list(it)), 0)
        
        it = iter_vars_from_dotenv_chars("\t")
        self.assertEqual(len(list(it)), 0)
        
        it = iter_vars_from_dotenv_chars("\n".join([
            "",
            "KEY1=value1",
            "",
            "KEY2=value2",
            "\t",
            "\t\v",
            "KEY3=value3",
            "",
        ]))
        self.assertEqual(next(it), Var("KEY1", "value1"))
        self.assertEqual(next(it), Var("KEY2", "value2"))
        self.assertEqual(next(it), Var("KEY3", "value3"))

    def test_parses_multiple_key_value_pairs(self):
        it = iter_vars_from_dotenv_chars("\n".join([
            "KEY1=value1",
            "KEY2=value2",
            'KEY3="value3"',
            "KEY4='value4'",
            "'KEY5'=value5",
        ]))
        self.assertEqual(next(it), Var("KEY1", "value1"))
        self.assertEqual(next(it), Var("KEY2", "value2"))
        self.assertEqual(next(it), Var("KEY3", "value3"))
        self.assertEqual(next(it), Var("KEY4", "value4"))
        self.assertEqual(next(it), Var("KEY5", "value5"))

    def test_parses_comments(self):
        it = iter_vars_from_dotenv_chars("\n".join([
            "KEY1=value1",
            "# Comment on separate line",
            "KEY2=value2 # Comment after unquoted value",
            'KEY3="value3"# Comment after double-quoted value',
            "KEY4='value4'# Comment after single-quoted value",
            "KEY5=# Commend after empty value"
        ]))
        self.assertEqual(next(it), Var("KEY1", "value1"))
        self.assertEqual(next(it), Var("KEY2", "value2"))
        self.assertEqual(next(it), Var("KEY3", "value3"))
        self.assertEqual(next(it), Var("KEY4", "value4"))
        self.assertEqual(next(it), Var("KEY5", ""))


if __name__ == "__main__":
    unittest.main()
