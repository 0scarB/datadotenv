from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from contextlib import contextmanager
from fractions import Fraction
import os
from pathlib import Path
import shutil
from typing import cast, Generator, Literal, NewType, Optional, Union, TypeAlias
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
            spec.from_([
                'STR_VAR="foo"',
                'BOOL_VAR1=True',
                "BOOL_VAR2='true'",
                'BOOL_VAR3="False"',
                'BOOL_VAR4=false',
                'INT_VAR=42',
                'FLOAT_VAR=3.14',
                'UNSET_VAR=',
            ]),
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

    def test_instantiates_dataclass_with_sequence_types(self):

        @dataclass
        class MyDotenv:
            list1: list[str]
            list2: list[bool]
            list3: list[int]
            list4: list[float]
            list5: list[str]
            same_type_tuple: tuple[float, float]
            multi_type_tuple: tuple[int, float, str]
            single_value_tuple: tuple[bool]

        self.assertEqual(
            datadotenv(MyDotenv).from_([
                # Test empty list
                'LIST1=',
                # Test list with single value
                'LIST2=True',
                # Test multi value list
                'LIST3="1, 2,3"',
                'LIST4=1,2,3',
                # Test list with empty str
                'LIST5=""',
                'SAME_TYPE_TUPLE=1,0.5',
                'MULTI_TYPE_TUPLE="1, 0.5, foo"',
                'SINGLE_VALUE_TUPLE=False',
            ]),
            MyDotenv(
                list1=[],
                list2=[True],
                list3=[1, 2, 3],
                list4=[1., 2., 3.],
                list5=[""],
                same_type_tuple=(1., 0.5),
                multi_type_tuple=(1, 0.5, "foo"),
                single_value_tuple=(False,),
            )
        )

        # Test alternate separator
        self.assertEqual(
            datadotenv(MyDotenv, sequence_separator="|").from_([
                # Test empty list
                'LIST1=',
                # Test list with single value
                'LIST2=True',
                # Test multi value list
                'LIST3="1| 2|3"',
                'LIST4=1|2|3',
                # Test list with empty str
                'LIST5=""',
                'SAME_TYPE_TUPLE=1|0.5',
                'MULTI_TYPE_TUPLE="1| 0.5| foo"',
                'SINGLE_VALUE_TUPLE=False',
            ]),
            MyDotenv(
                list1=[],
                list2=[True],
                list3=[1, 2, 3],
                list4=[1., 2., 3.],
                list5=[""],
                same_type_tuple=(1., 0.5),
                multi_type_tuple=(1, 0.5, "foo"),
                single_value_tuple=(False,),
            )
        )

        # Test trim_sequence_items works as expected
        @dataclass
        class MyDotenv:
            tup: tuple[str, str]
        self.assertEqual(
            datadotenv(MyDotenv).from_("TUP='foo, bar'"),
            MyDotenv(tup=("foo", "bar")),
        )
        self.assertEqual(
            datadotenv(MyDotenv, trim_sequence_items=True).from_("TUP='foo, bar'"),
            MyDotenv(tup=("foo", "bar")),
        )
        self.assertEqual(
            datadotenv(MyDotenv, trim_sequence_items=False).from_("TUP='foo, bar'"),
            MyDotenv(tup=("foo", " bar")),
        )

    def test_instantiates_dataclass_with_literal_types(self):

        @dataclass(frozen=True)
        class MyDotenv:
            literal_var1: Literal["foo", 42]
            literal_var2: Literal["foo", 42]

        spec = datadotenv(MyDotenv)

        self.assertEqual(
            spec.from_([
                'LITERAL_VAR1="foo"',
                'LITERAL_VAR2=42',
            ]),
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
        datacls = spec.from_([
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
        ])

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
            spec.from_(""),
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
            spec.from_([
                "STR_VAR=bar",
                "INT_VAR=420",
                "FLOAT_VAR=2.71",
                "NONE_VAR=",
                "LITERAL_VAR=bar",
            ]),
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
            datadotenv(MyDotenv).from_([
                'FILE_PATH=./non-existent'
            ])

        # Test resolves path by default
        self.assertEqual(
            datadotenv(MyDotenv).from_([
                'FILE_PATH=./src/../src'
            ]),
            MyDotenv(Path("./src").resolve())
        )

        # Test option not not resolve 
        self.assertEqual(
            datadotenv(MyDotenv, resolve_file_paths=False).from_([
                'FILE_PATH=./src'
            ]),
            MyDotenv(Path("./src"))
        )

        # Test option to not check existence
        self.assertEqual(
            datadotenv(MyDotenv, file_paths_must_exist=False).from_([
                'FILE_PATH=./non-existent'
            ]),
            MyDotenv(file_path=Path("./non-existent").resolve())
        )

    def test_handles_dataclasses_with_datetimes(self):

        @dataclass(frozen=True)
        class MyDotenv:
            time: datetime
        
        self.assertEqual(
            datadotenv(MyDotenv).from_([
                'TIME="1989-11-09 19:00"'
            ]),
            MyDotenv(datetime(year=1989, month=11, day=9, hour=19)),
        )

        with self.assertRaises(datadotenv.error.CannotParse) as err_ctx:
            datadotenv(MyDotenv).from_([
                'TIME="198x-11-09 19:00"',
            ]),
        self.assertEqual(
            str(err_ctx.exception), 
            "Cannot parse datetime: Invalid isoformat string: '198x-11-09 19:00'"
        )
        
    def test_handles_dataclasses_with_dates(self):

        @dataclass(frozen=True)
        class MyDotenv:
            day: date
        
        self.assertEqual(
            datadotenv(MyDotenv).from_([
                'DAY="1989-11-09"'
            ]),
            MyDotenv(date(year=1989, month=11, day=9)),
        )

        with self.assertRaises(datadotenv.error.CannotParse) as err_ctx:
            datadotenv(MyDotenv).from_([
                'DAY="198x-11-09"',
            ]),
        self.assertEqual(
            str(err_ctx.exception), 
            "Cannot parse date: Invalid isoformat string: '198x-11-09'"
        )

    def test_handles_dataclasses_with_timedeltas(self):
        
        @dataclass(frozen=True)
        class MyDotenv:
            delta: timedelta
        
        self.assertEqual(
            datadotenv(MyDotenv).from_([
                'DELTA="1h 30m"'
            ]),
            MyDotenv(timedelta(hours=1, minutes=30)),
        )

        with self.assertRaises(datadotenv.error.CannotParse):
            datadotenv(MyDotenv).from_([
                'DELTA="1h 30n"',
            ]),

    def test_supports_different_casing_options(self):

        @dataclass(frozen=True)
        class MyDotenv:
            normal_casing: str
            mixed_CASING: str
        
        # Test defaults to uppercase
        self.assertEqual(
            datadotenv(MyDotenv).from_([
                'NORMAL_CASING=foo',
                'MIXED_CASING=bar',
            ]),
            MyDotenv(
                normal_casing="foo",
                mixed_CASING="bar",
            )
        )
        
        # Test explicit uppercase
        self.assertEqual(
            datadotenv(MyDotenv, case="upper").from_([
                'NORMAL_CASING=foo',
                'MIXED_CASING=bar',
            ]),
            MyDotenv(
                normal_casing="foo",
                mixed_CASING="bar",
            )
        )
        
        # Test lowercase
        self.assertEqual(
            datadotenv(MyDotenv, case="lower").from_([
                'normal_casing=foo',
                'mixed_casing=bar',
            ]),
            MyDotenv(
                normal_casing="foo",
                mixed_CASING="bar",
            )
        )
        
        # Test preserve casing
        self.assertEqual(
            datadotenv(MyDotenv, case="preserve").from_([
                'normal_casing=foo',
                'mixed_CASING=bar',
            ]),
            MyDotenv(
                normal_casing="foo",
                mixed_CASING="bar",
            )
        )

        # Test ignore casing
        self.assertEqual(
            datadotenv(MyDotenv, case="ignore").from_([
                'nOrMaL_cAsInG=foo',
                'MiXeD_cAsInG=bar',
            ]),
            MyDotenv(
                normal_casing="foo",
                mixed_CASING="bar",
            )
        )

    def test_supports_different_options_for_complete_or_incomplete_description_of_dotenv(
            self,
    ):

        @dataclass(frozen=True)
        class MyDotenv:
            var: str

        # Test default: dataclass must fully describe dotenv
        with self.assertRaises(datadotenv.error.VariableNotSpecified):
            datadotenv(MyDotenv).from_([
                'VAR=foo',
                'NOT_DESCRIBED_IN_DATACLASS=bar',
            ]),
            
        # Test explicit: dataclass must fully describe dotenv
        # using `allow_incomplete=False`
        with self.assertRaises(datadotenv.error.VariableNotSpecified):
            datadotenv(MyDotenv, allow_incomplete=False).from_([
                'VAR=foo',
                'NOT_DESCRIBED_IN_DATACLASS=bar',
            ])

        # Test can accept incomplete dataclass with `allow_incomplete=True` 
        self.assertEqual(
            datadotenv(MyDotenv, allow_incomplete=True).from_([
                'VAR=foo',
                'NOT_DESCRIBED_IN_DATACLASS=bar',
            ]),
            MyDotenv(var="foo")
        )

    def test_can_validate_fields_with_validate_parameter(self):
        
        @dataclass
        class MyDotenv:
            system_port: int
            ephemeral_port: int

        def is_positive(x: int) -> bool:
            return x >= 0

        def validate_not_reserved_for_database(port: int) -> str | None:
            if port == 5432:
                return "Reserved for postgreSQL database!"

        spec = datadotenv(
            MyDotenv,
            validate=[
                ("system_port", lambda port: port < 1024),
                ("ephemeral_port", lambda port: 1023 < port < 65536),
                ("system_port", is_positive),
                ("ephemeral_port", is_positive),
                ("ephemeral_port", validate_not_reserved_for_database),
            ]
        )

        self.assertEqual(
            spec.from_([
                "SYSTEM_PORT=80",
                "EPHEMERAL_PORT=8080",
            ]),
            MyDotenv(
                system_port=80,
                ephemeral_port=8080,
            )
        )

        with self.assertRaises(datadotenv.error.InvalidValue):
            spec.from_([
                "SYSTEM_PORT=8080",
                "EPHEMERAL_PORT=8080",
            ])

        with self.assertRaises(datadotenv.error.InvalidValue):
            spec.from_([
                "SYSTEM_PORT=80",
                "EPHEMERAL_PORT=80",
            ])

        with self.assertRaises(datadotenv.error.InvalidValue):
            spec.from_([
                "SYSTEM_PORT=-1",
                "EPHEMERAL_PORT=80",
            ])

        with self.assertRaises(datadotenv.error.InvalidValue) as err_ctx:
            spec.from_([
                "SYSTEM_PORT=80",
                "EPHEMERAL_PORT=5432",
            ])
        self.assertEqual(
            str(err_ctx.exception),
            "Reserved for postgreSQL database!"
        )

    def test_can_validate_fields_with_validate_method_chaining(self):
        
        @dataclass
        class MyDotenv:
            system_port: int
            ephemeral_port: int

        def is_positive(x: int) -> bool:
            return x >= 0

        def validate_not_reserved_for_database(port: int) -> str | None:
            if port == 5432:
                return "Reserved for postgreSQL database!"

        spec = datadotenv(MyDotenv)\
            .validate("system_port", lambda port: port < 1024)\
            .validate("ephemeral_port", lambda port: 1023 < port < 65536)\
            .validate("system_port", is_positive)\
            .validate("ephemeral_port", is_positive)\
            .validate("ephemeral_port", validate_not_reserved_for_database)

        self.assertEqual(
            spec.from_([
                "SYSTEM_PORT=80",
                "EPHEMERAL_PORT=8080",
            ]),
            MyDotenv(
                system_port=80,
                ephemeral_port=8080,
            )
        )

        with self.assertRaises(datadotenv.error.InvalidValue):
            spec.from_([
                "SYSTEM_PORT=8080",
                "EPHEMERAL_PORT=8080",
            ])

        with self.assertRaises(datadotenv.error.InvalidValue):
            spec.from_([
                "SYSTEM_PORT=80",
                "EPHEMERAL_PORT=80",
            ])

        with self.assertRaises(datadotenv.error.InvalidValue):
            spec.from_([
                "SYSTEM_PORT=-1",
                "EPHEMERAL_PORT=80",
            ])

        with self.assertRaises(datadotenv.error.InvalidValue) as err_ctx:
            spec.from_([
                "SYSTEM_PORT=80",
                "EPHEMERAL_PORT=5432",
            ])
        self.assertEqual(
            str(err_ctx.exception),
            "Reserved for postgreSQL database!"
        )

    def test_can_retarget_different_dataclass_fields_with_retarget_parameter(self):

        @dataclass
        class MyDotenv:
            port: int
            domain: str

        spec = datadotenv(
            MyDotenv,
            retarget=[
                ("port", "SERVER_PORT"),
                ("DOMAIN", "SERVER_DOMAIN"),
            ],
        )

        self.assertEqual(
            spec.from_([
                'SERVER_PORT=443',
                'SERVER_DOMAIN=example.com',
            ]),
            MyDotenv(
                port=443,
                domain="example.com",
            )
        )

        # Test that old names are no longer valid
        with self.assertRaises(datadotenv.error.VariableNotSpecified):
            spec.from_([
                'PORT=443',
                'SERVER_DOMAIN=example.com',
            ])
        with self.assertRaises(datadotenv.error.VariableNotSpecified):
            spec.from_([
                'SERVER_PORT=443',
                'DOMAIN=example.com',
            ])

    def test_can_retarget_different_dataclass_fields_with_retarget_method_chaining(self):

        @dataclass
        class MyDotenv:
            port: int
            domain: str

        spec = datadotenv(MyDotenv)\
            .retarget("port", "SERVER_PORT")\
            .retarget("DOMAIN", "SERVER_DOMAIN")

        self.assertEqual(
            spec.from_([
                'SERVER_PORT=443',
                'SERVER_DOMAIN=example.com',
            ]),
            MyDotenv(
                port=443,
                domain="example.com",
            )
        )

        # Test that old names are no longer valid
        with self.assertRaises(datadotenv.error.VariableNotSpecified):
            spec.from_([
                'PORT=443',
                'SERVER_DOMAIN=example.com',
            ])
        with self.assertRaises(datadotenv.error.VariableNotSpecified):
            spec.from_([
                'SERVER_PORT=443',
                'DOMAIN=example.com',
            ])

    def test_can_convert_custom_types_with_handle_types_parameter(self):

        class CustomClass:
            pass

        class CustomSubClass(CustomClass):
            pass

        custom_cls_inst = CustomClass()
        custom_sub_cls_inst = CustomSubClass()
        custom_cls_insts = [
            custom_cls_inst,
            custom_sub_cls_inst,
        ]

        CustomType = NewType("CustomType", str)

        SystemPort = NewType("SystemPort", int)
        EphemeralPort = NewType("EphemalPort", int)

        system_port_type_converter = datadotenv.ConvertType(
            SystemPort,
            lambda s: int(s),
            validate=lambda port: port < 1024,
        )
        ephemeral_port_type_converter = datadotenv.ConvertType(
            EphemeralPort,
            lambda s: int(s),
            validate=lambda port: 1024 < port < 65536,
        )

        IntDefaultMinusOne = NewType("IntDefault0", int)

        @dataclass(frozen=True)
        class MyDotenv:
            inst_of_custom_cls: CustomClass
            inst_of_custom_cls2: CustomClass
            frac: Fraction
            inst_of_custom_type: CustomType
            prod_port: SystemPort
            dev_port: EphemeralPort
            custom_int1: IntDefaultMinusOne
            custom_int2: IntDefaultMinusOne

        self.assertEqual(
            datadotenv(
                MyDotenv, 
                convert_types=[
                    (CustomClass, lambda _: custom_cls_insts.pop(0)),
                    (
                        Fraction, 
                        lambda s: Fraction(int(s.split("/")[0]), int(s.split("/")[1]))
                    ),
                    (CustomType, lambda _: "CustomType"),
                    system_port_type_converter,
                    ephemeral_port_type_converter,
                    datadotenv.ConvertType(
                        IntDefaultMinusOne, 
                        lambda s: int(s),
                        default_if_unset=cast(IntDefaultMinusOne, -1),
                    ),
                ]
            ).from_([
                'INST_OF_CUSTOM_CLS=foo',
                'INST_OF_CUSTOM_CLS2=bar',
                'FRAC=3/4',
                'INST_OF_CUSTOM_TYPE=baz',
                'PROD_PORT=80',
                'DEV_PORT=8080',
                'CUSTOM_INT1=42',
                'CUSTOM_INT2=',
            ]),
            MyDotenv(
                inst_of_custom_cls=custom_cls_inst,
                inst_of_custom_cls2=custom_sub_cls_inst,
                frac=Fraction(3, 4),
                inst_of_custom_type=cast(CustomType, "CustomType"),
                prod_port=cast(SystemPort, 80),
                dev_port=cast(EphemeralPort, 8080),
                custom_int1=cast(IntDefaultMinusOne, 42),
                custom_int2=cast(IntDefaultMinusOne, -1),
            )
        )

        @dataclass
        class MyDotenv:
            system_port: SystemPort
            ephemeral_port: EphemeralPort

        with self.assertRaises(datadotenv.error.InvalidValue):
            datadotenv(
                MyDotenv,
                convert_types=[
                    system_port_type_converter,
                    ephemeral_port_type_converter,
                ],
            ).from_([
                'SYSTEM_PORT=8080',
                'EPHEMERAL_PORT=8080',
            ])

        with self.assertRaises(datadotenv.error.InvalidValue):
            datadotenv(
                MyDotenv, 
                convert_types=[
                    system_port_type_converter,
                    ephemeral_port_type_converter,
                ],
            ).from_([
                'SYSTEM_PORT=80',
                'EPHEMERAL_PORT=80',
            ])

    def test_can_convert_custom_types_with_convert_type_method_chaining(self):
        
        class CustomClass:
            pass

        class CustomSubClass(CustomClass):
            pass

        custom_cls_inst = CustomClass()
        custom_sub_cls_inst = CustomSubClass()
        custom_cls_insts = [
            custom_cls_inst,
            custom_sub_cls_inst,
        ]

        CustomType = NewType("CustomType", str)

        SystemPort = NewType("SystemPort", int)
        EphemeralPort = NewType("EphemalPort", int)

        IntDefaultMinusOne = NewType("IntDefault0", int)

        @dataclass(frozen=True)
        class MyDotenv:
            inst_of_custom_cls: CustomClass
            inst_of_custom_cls2: CustomClass
            frac: Fraction
            inst_of_custom_type: CustomType
            prod_port: SystemPort
            dev_port: EphemeralPort
            custom_int1: IntDefaultMinusOne
            custom_int2: IntDefaultMinusOne

        self.assertEqual(
            datadotenv(MyDotenv)\
                .convert_type(CustomClass, lambda _: custom_cls_insts.pop(0))\
                .convert_type(
                    Fraction, 
                    lambda s: Fraction(int(s.split("/")[0]), int(s.split("/")[1]))
                )\
                .convert_type(CustomType, lambda _: "CustomType")\
                .convert_type(
                    ("check", lambda t: t in {SystemPort, EphemeralPort}),
                    lambda s: int(s),
                )\
                .convert_type(
                    IntDefaultMinusOne, 
                    lambda s: int(s), 
                    default_if_unset=cast(IntDefaultMinusOne, -1)
                )\
                .from_([
                    'INST_OF_CUSTOM_CLS=foo',
                    'INST_OF_CUSTOM_CLS2=bar',
                    'FRAC=3/4',
                    'INST_OF_CUSTOM_TYPE=baz',
                    'PROD_PORT=80',
                    'DEV_PORT=8080',
                    'CUSTOM_INT1=42',
                    'CUSTOM_INT2=',
                ]),
            MyDotenv(
                inst_of_custom_cls=custom_cls_inst,
                inst_of_custom_cls2=custom_sub_cls_inst,
                frac=Fraction(3, 4),
                inst_of_custom_type=cast(CustomType, "CustomType"),
                prod_port=cast(SystemPort, 80),
                dev_port=cast(EphemeralPort, 8080),
                custom_int1=cast(IntDefaultMinusOne, 42),
                custom_int2=cast(IntDefaultMinusOne, -1),
            )
        )

        @dataclass
        class MyDotenv:
            system_port: SystemPort
            ephemeral_port: EphemeralPort

        with self.assertRaises(datadotenv.error.InvalidValue):
            datadotenv(MyDotenv)\
                .convert_type(
                    SystemPort,
                    lambda s: int(s),
                    validate=lambda port: port < 1024,
                ).convert_type(
                    EphemeralPort,
                    lambda s: int(s),
                    validate=lambda port: 1023 < port < 65536,
                ).from_([
                    'SYSTEM_PORT=8080',
                    'EPHEMERAL_PORT=8080',
                ])

        with self.assertRaises(datadotenv.error.InvalidValue):
            datadotenv(MyDotenv)\
                .convert_type(
                    SystemPort,
                    lambda s: int(s),
                    validate=lambda port: port < 1024,
                ).convert_type(
                    EphemeralPort,
                    lambda s: int(s),
                    validate=lambda port: 1023 < port < 65536,
                ).from_([
                    'SYSTEM_PORT=80',
                    'EPHEMERAL_PORT=80',
                ])

    def test_can_convert_fields_using_convert_parameter(self):

        @dataclass
        class MyDotenv:
            decimal: Decimal
            positive_decimal: Decimal

        spec = datadotenv(
            MyDotenv,
            convert=[
                ("decimal", lambda s: Decimal(s)),
                datadotenv.Convert(
                    "positive_decimal",
                    lambda s: Decimal(s),
                    validate=lambda x: x >= 0,
                )
            ]
        )

        self.assertEqual(
            spec.from_([
                'DECIMAL=-3.14',
                'POSITIVE_DECIMAL=3.14',
            ]),
            MyDotenv(
                decimal=Decimal("-3.14"),
                positive_decimal=Decimal("3.14"),
            ),
        )

        # Test validate argument
        with self.assertRaises(datadotenv.error.InvalidValue):
            spec.from_([
                'DECIMAL=-3.14',
                'POSITIVE_DECIMAL=-3.14',
            ])

        # Test does not allow duplicates in convert
        with self.assertRaises(ValueError):
            spec = datadotenv(
                MyDotenv,
                convert=[
                    ("decimal", lambda s: Decimal(s)),
                    datadotenv.Convert(
                        "positive_decimal",
                        lambda s: Decimal(s),
                        validate=lambda x: x >= 0,
                    ),
                    ("positive_decimal", lambda s: s),
                ]
            )

    def test_can_convert_fields_using_convert_method_chaining(self):

        @dataclass
        class MyDotenv:
            decimal: Decimal
            positive_decimal: Decimal

        spec = datadotenv(MyDotenv)\
            .convert("decimal", lambda s: Decimal(s))\
            .convert(
                "positive_decimal",
                lambda s: Decimal(s),
                validate=lambda x: x >= 0,
            )

        self.assertEqual(
            spec.from_([
                'DECIMAL=-3.14',
                'POSITIVE_DECIMAL=3.14',
            ]),
            MyDotenv(
                decimal=Decimal("-3.14"),
                positive_decimal=Decimal("3.14"),
            ),
        )

        # Test validate argument
        with self.assertRaises(datadotenv.error.InvalidValue):
            spec.from_([
                'DECIMAL=-3.14',
                'POSITIVE_DECIMAL=-3.14',
            ])

        # Test does not allow duplicates in convert
        with self.assertRaises(ValueError):
            spec = datadotenv(MyDotenv)\
                .convert("decimal", lambda s: Decimal(s))\
                .convert(
                  "positive_decimal",
                  lambda s: Decimal(s),
                  validate=lambda x: x >= 0,
                )\
                .convert("positive_decimal", lambda s: s)

    def test_can_read_from_files(self):

        # Test file path

        @dataclass
        class MyDotenv:
            var: int

        with _create_test_fs_entry(".env", [
            'VAR=1',
        ]) as file_path:
            self.assertEqual(
                datadotenv(MyDotenv).from_(file_path),
                MyDotenv(var=1),
            )

        # Test file path string

        @dataclass
        class MyDotenv:
            var: int
        
        with _create_test_fs_entry(".env", [
            'VAR=1',
        ]) as file_path:
            self.assertEqual(
                datadotenv(MyDotenv).from_(str(file_path)),
                MyDotenv(var=1),
            )

        # Test directory path

        @dataclass
        class MyDotenv:
            var: int
            secret_token: str

        with _create_test_fs_entry("dir/", [
            (".env", [
                'VAR=1',
            ]),
            (".env.secret", [
                'SECRET_TOKEN=password1234',
            ]),
        ]) as dir_path:
            self.assertEqual(
                datadotenv(MyDotenv).from_(dir_path),
                MyDotenv(
                    var=1,
                    secret_token="password1234",
                ),
            )

        # Test directory path string

        @dataclass
        class MyDotenv:
            var: int
            secret_token: str

        with _create_test_fs_entry("dir/", [
            (".env", [
                'VAR=1',
            ]),
            (".env.secret", [
                'SECRET_TOKEN=password1234',
            ]),
        ]) as dir_path:
            self.assertEqual(
                datadotenv(MyDotenv).from_(str(dir_path)),
                MyDotenv(
                    var=1,
                    secret_token="password1234",
                ),
            )

        # Test .env.secret overrides .env

        @dataclass
        class MyDotenv:
            var: int
            secret_token: str

        with _create_test_fs_entry("dir/", [
            (".env", [
                'VAR=1',
                'SECRET_TOKEN="Placeholder! Please replace with something secure."'
            ]),
            (".env.secret", [
                'SECRET_TOKEN=password1234',
            ]),
        ]) as dir_path:
            self.assertEqual(
                datadotenv(MyDotenv).from_(dir_path),
                MyDotenv(
                    var=1,
                    secret_token="password1234",
                ),
            )

        # Test multiple manually specified files

        @dataclass
        class MyDotenv:
            server_host: str
            server_port: int
            secret_token: str

        with _create_test_fs_entry("dir/", [
            (".env", [
                'SERVER_HOST=http://127.0.0.1',
                'SERVER_PORT=8080',
                'SECRET_TOKEN="Placeholder! Please replace with something secure."'
            ]),
            (".env.prod", [
                'SERVER_HOST=https://xkcd.com',
                'SERVER_PORT=80',
            ]),
            (".env.secret", [
                'SECRET_TOKEN=password1234',
            ]),
        ]) as dir_path:
            self.assertEqual(
                datadotenv(MyDotenv).from_(
                    dir_path / ".env",
                    dir_path / ".env.secret",
                    str(dir_path / ".env.prod"),
                ),
                MyDotenv(
                    server_host="https://xkcd.com",
                    server_port=80,
                    secret_token="password1234",
                ),
            )

        # Test can find files relative to git root

        @dataclass
        class MyDotenv:
            var: int

        with _create_test_fs_entry(".env", [
            'VAR=1',
        ]) as file_path:
            dir_path = file_path.parent
            self.assertEqual(
                datadotenv(MyDotenv).from_(
                    f"<git-root>/{dir_path.name}/.env"
                ),
                MyDotenv(var=1),
            )

        @dataclass
        class MyDotenv:
            var: int

        project_path = Path(__file__).parent
        with _create_test_fs_entry(
                ".env.testy_mc_test", 
                ['VAR=1'], 
                parent_path=project_path,
                remove_dir=False,
        ) as file_path:
            dir_path = file_path.parent
            self.assertEqual(
                datadotenv(MyDotenv).from_("<gitroot>"),
                MyDotenv(var=1),
            )
            (project_path / ".env.testy_mc_test").unlink()

    def test_can_read_from_os_environ(self):
        
        @dataclass
        class MyDotenv:
            datadotenv_test_env_var: int

        os.environ["DATADOTENV_TEST_ENV_VAR"] = "1"

        self.assertEqual(
            datadotenv(MyDotenv, allow_incomplete=True).from_(
                os.environ,
            ),
            MyDotenv(datadotenv_test_env_var=1),
        )

        del os.environ["DATADOTENV_TEST_ENV_VAR"]

        # Test os.environ can override .env

        @dataclass
        class MyDotenv:
            from_dotenv_file: int
            datadotenv_test_env_var: int

        with _create_test_fs_entry(".env", [
            'FROM_DOTENV_FILE=1',
            'DATADOTENV_TEST_ENV_VAR=1',
        ]) as file_path:

            os.environ["DATADOTENV_TEST_ENV_VAR"] = "2"

            self.assertEqual(
                datadotenv(MyDotenv, allow_incomplete=True).from_(
                    file_path,
                    os.environ,
                ),
                MyDotenv(
                    from_dotenv_file=1,
                    datadotenv_test_env_var=2,
                ),
            )   

            del os.environ["DATADOTENV_TEST_ENV_VAR"]


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


FsEntryContentSpec: TypeAlias = list[
    str
    | tuple[
        str,
        list[
            tuple[
                str, 
                list[str]
            ] | tuple[
                str, 
                list[
                    tuple[
                        str,
                        list[str],
                    ] | tuple[
                        str,
                        list[tuple[str, list[str]]]
                    ]
                ]
            ]
        ]
    ]
]


@contextmanager
def _create_test_fs_entry(
        name: str,
        content: FsEntryContentSpec,
        remove_dir: bool = True,
        parent_path: Path | None = None,
) -> Generator[Path, None, None]:
    parent_dir_is_root = False
    if parent_path is None:
        parent_path = \
            Path(__file__).resolve().parent / f"test_dir{_generate_unique_id()}"
        if parent_path.exists():
            shutil.rmtree(parent_path)
        parent_path.mkdir()
        parent_dir_is_root = True

    is_file_spec = not (len(content) > 0 and type(content[0]) is not str)
    if is_file_spec:
        file_path: Path = parent_path / name
        if not file_path.parent.exists():
            file_path.parent.mkdir(parents=True)
        file_content = "\n".join(cast(tuple[str], content))
        with open(file_path, "w") as f:
            f.write(file_content)

        yield file_path
    else:
        dir_path: Path = parent_path / name
        dir_path.mkdir(parents=True)
        for child_name, child_content in content:
            with _create_test_fs_entry(
                child_name,
                cast(FsEntryContentSpec, child_content), 
                parent_path=dir_path,
            ): pass

        yield dir_path

    if parent_dir_is_root and remove_dir:
        shutil.rmtree(parent_path)


__unique_id: int = -1
def _generate_unique_id() -> int:
    global __unique_id
    __unique_id += 1
    return __unique_id


if __name__ == "__main__":
    unittest.main()

