from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Literal, Optional, Union
import unittest
from unittest import TestCase


from src import datadotenv, parse, Var


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

    def test_instantiates_dataclass_with_literal_types(self):

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

    def test_instantiates_dataclass_with_union_types(self):

        @dataclass(frozen=True)
        class MyDotenv:
            int_or_unset1: int | None
            int_or_unset2: Union[int, None]
            int_or_unset3: Optional[int]
            int_or_str1: int | str
            int_or_str2: Union[int, str]
            int_or_float1: int | float
            int_or_float2: int | float
            bool_or_int1: int | bool
            bool_or_int2: int | bool
            str_or_path1: Path | str
            str_or_path2: str | Path
            str_or_path3: str | Path

        spec = datadotenv(MyDotenv)
        datacls = spec.from_str("\n".join([
            'INT_OR_UNSET1=42',
            'INT_OR_UNSET2=',
            'INT_OR_UNSET3=',
            'INT_OR_STR1=42',
            'INT_OR_STR2=foo',
            'INT_OR_FLOAT1=3.14',
            'INT_OR_FLOAT2=3',
            'BOOL_OR_INT1=True',
            'BOOL_OR_INT2=0',
            'STR_OR_PATH1="src"',
            'STR_OR_PATH2="non-existent"',
            'STR_OR_PATH3="127.0.0.1"',
        ]))

        self.assertEqual(
            datacls,
            MyDotenv(
                int_or_unset1=42,
                int_or_unset2=None,
                int_or_unset3=None,
                int_or_str1=42,
                int_or_str2="foo",
                int_or_float1=3.14,
                int_or_float2=3,
                bool_or_int1=True,
                bool_or_int2=0,
                str_or_path1=Path("./src").resolve(),
                str_or_path2="non-existent",
                str_or_path3="127.0.0.1",
            )
        )
        self.assertEqual(type(datacls.int_or_float2), int)
        self.assertEqual(type(datacls.bool_or_int1), bool)
        self.assertEqual(type(datacls.bool_or_int2), int)

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
        self.assertEqual(
            datadotenv(MyDotenv, file_paths_must_exist=False).from_str("\n".join([
                'FILE_PATH=./non-existent'
            ])),
            MyDotenv(file_path=Path("./non-existent").resolve())
        )

    def test_handles_dataclasses_with_datetimes(self):

        @dataclass(frozen=True)
        class MyDotenv:
            time: datetime
        
        self.assertEqual(
            datadotenv(MyDotenv).from_str("\n".join([
                'TIME="1989-11-09 19:00"'
            ])),
            MyDotenv(datetime(year=1989, month=11, day=9, hour=19)),
        )

        with self.assertRaises(datadotenv.error.CannotParse) as err_ctx:
            datadotenv(MyDotenv).from_str("\n".join([
                'TIME="198x-11-09 19:00"'
            ])),
        self.assertEqual(
            str(err_ctx.exception), 
            "Cannot parse datetime: Invalid isoformat string: '198x-11-09 19:00'"
        )
        
    def test_handles_dataclasses_with_dates(self):

        @dataclass(frozen=True)
        class MyDotenv:
            day: date
        
        self.assertEqual(
            datadotenv(MyDotenv).from_str("\n".join([
                'DAY="1989-11-09"'
            ])),
            MyDotenv(date(year=1989, month=11, day=9)),
        )

        with self.assertRaises(datadotenv.error.CannotParse) as err_ctx:
            datadotenv(MyDotenv).from_str("\n".join([
                'DAY="198x-11-09"'
            ])),
        self.assertEqual(
            str(err_ctx.exception), 
            "Cannot parse date: Invalid isoformat string: '198x-11-09'"
        )

    def test_handles_dataclasses_with_timedeltas(self):
        
        @dataclass(frozen=True)
        class MyDotenv:
            delta: timedelta
        
        self.assertEqual(
            datadotenv(MyDotenv).from_str("\n".join([
                'DELTA="1h 30m"'
            ])),
            MyDotenv(timedelta(hours=1, minutes=30)),
        )

        with self.assertRaises(datadotenv.error.CannotParse):
            datadotenv(MyDotenv).from_str("\n".join([
                'DELTA="1h 30n"'
            ])),

    def test_supports_different_casing_options(self):

        @dataclass(frozen=True)
        class MyDotenv:
            normal_casing: str
            mixed_CASING: str
        
        # Test defaults to uppercase
        self.assertEqual(
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
        self.assertEqual(
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


class TestParseDotenvFromCharsIter(TestCase):

    def test_parses_unquoted_key_value_pair(self):
        it = parse.dotenv_from_chars_iter("KEY=value")
        self.assertEqual(next(it), Var("KEY", "value"))
        
        it = parse.dotenv_from_chars_iter("key=value")
        self.assertEqual(next(it), Var("key", "value"))
        
        it = parse.dotenv_from_chars_iter("KEY1=value")
        self.assertEqual(next(it), Var("KEY1", "value"))

        it = parse.dotenv_from_chars_iter("KEY =value")
        self.assertEqual(next(it), Var("KEY", "value"))

        it = parse.dotenv_from_chars_iter("KEY= value")
        self.assertEqual(next(it), Var("KEY", "value"))
        
        it = parse.dotenv_from_chars_iter("KEY = value")
        self.assertEqual(next(it), Var("KEY", "value"))
        
        it = parse.dotenv_from_chars_iter("KEY\t=\t\tvalue")
        self.assertEqual(next(it), Var("KEY", "value"))
        
        it = parse.dotenv_from_chars_iter(" KEY=value")
        self.assertEqual(next(it), Var("KEY", "value"))
        
        it = parse.dotenv_from_chars_iter("\tKEY=value")
        self.assertEqual(next(it), Var("KEY", "value"))
        
        it = parse.dotenv_from_chars_iter("\nKEY=value")
        self.assertEqual(next(it), Var("KEY", "value"))
        
        it = parse.dotenv_from_chars_iter("KEY=value ")
        self.assertEqual(next(it), Var("KEY", "value"))
        
        it = parse.dotenv_from_chars_iter("KEY=value\t")
        self.assertEqual(next(it), Var("KEY", "value"))
        
        it = parse.dotenv_from_chars_iter("KEY=value\n")
        self.assertEqual(next(it), Var("KEY", "value"))

    def test_parses_doubly_quoted_values(self):
        it = parse.dotenv_from_chars_iter('KEY="value"')
        self.assertEqual(next(it), Var("KEY", "value"))
        
        it = parse.dotenv_from_chars_iter('KEY=" value"')
        self.assertEqual(next(it), Var("KEY", " value"))
        
        it = parse.dotenv_from_chars_iter('KEY="value "')
        self.assertEqual(next(it), Var("KEY", "value "))
        
        it = parse.dotenv_from_chars_iter('KEY= "value"')
        self.assertEqual(next(it), Var("KEY", "value"))
        
        it = parse.dotenv_from_chars_iter('KEY="value" ')
        self.assertEqual(next(it), Var("KEY", "value"))

        it = parse.dotenv_from_chars_iter('KEY="value with \'single-quotes\'"')
        self.assertEqual(next(it), Var("KEY", "value with 'single-quotes'"))
        
        it = parse.dotenv_from_chars_iter(r'KEY="value with escaped \"double-quotes\""')
        self.assertEqual(next(it), Var("KEY", 'value with escaped "double-quotes"'))
        
        it = parse.dotenv_from_chars_iter(r'KEY="value with escaped \nnewline"')
        self.assertEqual(next(it), Var("KEY", "value with escaped \nnewline"))
        
        it = parse.dotenv_from_chars_iter(r'KEY="value with escaped\ttab"')
        self.assertEqual(next(it), Var("KEY", "value with escaped\ttab"))
        
        it = parse.dotenv_from_chars_iter(r'KEY="value with escaped \\ backslash"')
        self.assertEqual(next(it), Var("KEY", "value with escaped \\ backslash"))
        
        it = parse.dotenv_from_chars_iter('KEY= "value"')
        self.assertEqual(next(it), Var("KEY", "value"))
        
        it = parse.dotenv_from_chars_iter('KEY="value" ')
        self.assertEqual(next(it), Var("KEY", "value"))

        it = parse.dotenv_from_chars_iter('KEY="value with \'single-quotes\'"')
        self.assertEqual(next(it), Var("KEY", "value with 'single-quotes'"))
        
        it = parse.dotenv_from_chars_iter(r'KEY="value with escaped \"double-quotes\""')
        self.assertEqual(next(it), Var("KEY", 'value with escaped "double-quotes"'))
        
        it = parse.dotenv_from_chars_iter(r'KEY="value with escaped \nnewline"')
        self.assertEqual(next(it), Var("KEY", "value with escaped \nnewline"))
        
        it = parse.dotenv_from_chars_iter(r'KEY="value with escaped\ttab"')
        self.assertEqual(next(it), Var("KEY", "value with escaped\ttab"))
        
        it = parse.dotenv_from_chars_iter(r'KEY="value with escaped \\ backslash"')
        self.assertEqual(next(it), Var("KEY", "value with escaped \\ backslash"))
        
        it = parse.dotenv_from_chars_iter(r'KEY="value with escaped \' single-quote"')
        self.assertEqual(next(it), Var("KEY", "value with escaped ' single-quote"))
        
        it = parse.dotenv_from_chars_iter(r'KEY="value with escaped \r\nCR LF"')
        self.assertEqual(next(it), Var("KEY", "value with escaped \r\nCR LF"))
        
        it = parse.dotenv_from_chars_iter(r'KEY="value with escaped \r\nCR LF"')
        self.assertEqual(next(it), Var("KEY", "value with escaped \r\nCR LF"))

    def test_parses_singly_quoted_values(self):
        it = parse.dotenv_from_chars_iter("KEY='value'")
        self.assertEqual(next(it), Var("KEY", "value")) 
        
        it = parse.dotenv_from_chars_iter("KEY=' value'")
        self.assertEqual(next(it), Var("KEY", " value")) 
        
        it = parse.dotenv_from_chars_iter("KEY='value '")
        self.assertEqual(next(it), Var("KEY", "value ")) 
        
        it = parse.dotenv_from_chars_iter("KEY= 'value'")
        self.assertEqual(next(it), Var("KEY", "value")) 
        
        it = parse.dotenv_from_chars_iter("KEY='value' ")
        self.assertEqual(next(it), Var("KEY", "value")) 
        
        it = parse.dotenv_from_chars_iter(r"KEY='value with escaped backslash \\'")
        self.assertEqual(next(it), Var("KEY", "value with escaped backslash \\")) 
        
        it = parse.dotenv_from_chars_iter(r"KEY='value with escaped quote \''")
        self.assertEqual(next(it), Var("KEY", "value with escaped quote '")) 

    def test_parses_unset_values(self):
        it = parse.dotenv_from_chars_iter("KEY=")
        self.assertEqual(next(it), Var("KEY", None))
        
        it = parse.dotenv_from_chars_iter("KEY= ")
        self.assertEqual(next(it), Var("KEY", None))
        
        it = parse.dotenv_from_chars_iter("KEY=\t")
        self.assertEqual(next(it), Var("KEY", None))
        
        it = parse.dotenv_from_chars_iter("KEY=\n")
        self.assertEqual(next(it), Var("KEY", None))
        
        it = parse.dotenv_from_chars_iter("KEY=\t\n")
        self.assertEqual(next(it), Var("KEY", None))

    def test_parses_empty_strings(self):
        it = parse.dotenv_from_chars_iter('KEY=""')
        self.assertEqual(next(it), Var("KEY", ""))

    def test_parses_blank_lines_and_empty_string(self):
        it = parse.dotenv_from_chars_iter("")
        self.assertEqual(len(list(it)), 0)
        
        it = parse.dotenv_from_chars_iter("\n")
        self.assertEqual(len(list(it)), 0)
        
        it = parse.dotenv_from_chars_iter("\t")
        self.assertEqual(len(list(it)), 0)
        
        it = parse.dotenv_from_chars_iter("\n".join([
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
        it = parse.dotenv_from_chars_iter("\n".join([
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
        it = parse.dotenv_from_chars_iter("\n".join([
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


class TestParseTimedelta(TestCase):

    def test_success_cases(self):
        for s, delta in [
            # Common cases
            ("1ms", timedelta(milliseconds=1)),
            ("100ms", timedelta(milliseconds=100)),
            ("500ms", timedelta(milliseconds=500)),
            ("1s", timedelta(seconds=1)),
            ("-1s", timedelta(seconds=-1)),
            ("5s", timedelta(seconds=5)),
            ("10s", timedelta(seconds=10)),
            ("20s", timedelta(seconds=20)),
            ("30s", timedelta(seconds=30)),
            ("60s", timedelta(seconds=60)),
            ("0.5s", timedelta(milliseconds=500)),
            (".5s", timedelta(milliseconds=500)),
            ("1m", timedelta(minutes=1)),
            ("10m", timedelta(minutes=10)),
            ("15m", timedelta(minutes=15)),
            ("20m", timedelta(minutes=20)),
            ("30m", timedelta(minutes=30)),
            ("45m", timedelta(minutes=45)),
            ("1h", timedelta(hours=1)),
            ("2h", timedelta(hours=2)),
            ("6h", timedelta(hours=6)),
            ("12h", timedelta(hours=12)),
            ("24h", timedelta(days=1)),
            ("48h", timedelta(days=2)),
            ("72h", timedelta(days=3)),
            ("0.5h", timedelta(minutes=30)),
            (".5h", timedelta(minutes=30)),
            ("1.5h", timedelta(hours=1, minutes=30)),
            ("1h30m", timedelta(hours=1, minutes=30)),
            ("1h 30m", timedelta(hours=1, minutes=30)),
            ("2d12h", timedelta(days=2, hours=12)),
            ("2d 12h", timedelta(days=2, hours=12)),
            ("2d12h30m", timedelta(days=2, hours=12, minutes=30)),
            ("2d 12h 30m", timedelta(days=2, hours=12, minutes=30)),
            ("2d,12h 30m", timedelta(days=2, hours=12, minutes=30)),
            # Exhaustive cases
            ("1w2d3h4m5s6ms7us", timedelta(weeks=1, days=2, hours=3, minutes=4, seconds=5, milliseconds=6, microseconds=7)),
            (" 1w 2d, 3h ,4m , 5s\t6ms  7us\t", timedelta(weeks=1, days=2, hours=3, minutes=4, seconds=5, milliseconds=6, microseconds=7)),
        ]:
            self.assertEqual(
                parse.timedelta(s), delta
            )
            
    def test_failure_cases(self):
        for s in [
            "",
            "1s,",
            ",1s",
            "1 s",
            "1. s",
            "1. 5s",
        ]:
            with self.assertRaises(datadotenv.error.CannotParse):
                parse.timedelta(s)

            

if __name__ == "__main__":
    unittest.main()
