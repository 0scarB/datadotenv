from __future__ import annotations

import dataclasses
from dataclasses import dataclass
import datetime
from pathlib import Path
import types
import typing
from typing import (
    Any, 
    Callable, 
    cast, 
    ClassVar, 
    Generic, 
    Iterable, 
    Iterator, 
    Literal, 
    Protocol, 
    Self,
    Type, 
    TypeAlias, 
    TypeVar,
)


_T = TypeVar("_T")


class _Dataclass(Protocol):

    __dataclass_fields__: ClassVar[dict]


_TDataclass = TypeVar("_TDataclass", bound=_Dataclass)


_Casing: TypeAlias = Literal["upper", "lower", "preserve", "ignore"]


class _Datadotenv:
    error: _Error

    def __call__(
        self,
        datacls: Type[_TDataclass],
        /, *,
        case: _Casing = "upper",
        allow_incomplete: bool = False,
        file_paths_must_exist: bool = True,
        resolve_file_paths: bool = True,
        sequence_separator: str = ",",
        trim_sequence_items: bool = True,
        retarget: Iterable[tuple[str, str]] | None = None,
        validate: \
            Iterable[
                tuple[str, Callable[[Any], bool | str | Exception | None]]
            ] | None = None,
        convert_types: \
            Iterable[
                tuple[
                    tuple[Literal["check"], Callable[[Any], bool]] | Type[Any], 
                    Callable[[str], Any]
                ] | _Datadotenv.ConvertType[Any]
            ] | None = None,
        convert: \
            Iterable[
                tuple[str, Callable[[str], Any]]
                | _Datadotenv.Convert
            ] | None = None,
    ) -> _Spec[_TDataclass]:
        var_specs: list[_VarSpec[Any]] = []
        for field in dataclasses.fields(datacls):
            var_specs.append(_VarSpec(
                dataclass_field_name=field.name,
                dataclass_field_type=field.type,
                dotenv_var_name=_transform_case(case, field.name),
                default=field.default,
                target_strategy=_VarSpecTargetByName(
                    name=_transform_case(case, field.name),
                    ignore_case=case == "ignore",
                ),
                file_path_config=_VarSpecFilePathConfig(
                    resolve=resolve_file_paths,
                    must_exist=file_paths_must_exist,
                ),
                custom_convert=None,
                custom_validate=None,
                sequence_separator=sequence_separator,
                trim_sequence_items=trim_sequence_items,
            ))

        custom_validators_and_converters_specs: list[_ValidatorAndConverterSpec] = []
        if convert_types is not None:
            for convert_type in convert_types:
                custom_validators_and_converters_specs.append(
                    _create_validator_and_converter_spec(
                        convert_type,
                    )
                )

        spec = _Spec(
            datacls, 
            var_specs,
            allow_incomplete=allow_incomplete,
            custom_validators_and_converters_specs=custom_validators_and_converters_specs,
        )

        if retarget is not None:
            for old_name, new_name in retarget:
                spec.retarget(old_name, new_name)

        if validate is not None:
            for dotenv_var_name_or_dataclass_field_name, user_validate in validate:
                spec.validate(
                    dotenv_var_name_or_dataclass_field_name,
                    user_validate,
                )
        if convert is not None:
            for item in convert:
                if isinstance(item, _Datadotenv.Convert):
                    spec.convert(
                        item.name,
                        item.convert_str_to_type,
                        default_if_unset=item.default_if_unset,
                        validate=item.validate,
                    )
                else:
                    dotenv_var_name_or_dataclass_field_name, convert_str_to_type = item
                    spec.convert(
                        dotenv_var_name_or_dataclass_field_name,
                        convert_str_to_type,
                    )

        return spec

    def open_docs(self) -> None:
        """Opens the documentation in your browser."""
        url = "https://github.com/0scarB/datadotenv/tree/main"
        if not _check_system_supports_python_webbrowser():
            raise RuntimeError(
                "Could not open documentation URL in browser. "
                f"Manually visit {url}"
            )
        import webbrowser
        webbrowser.open(url)

    @dataclass
    class ConvertType(Generic[_T]):
        type_matcher: tuple[
            Literal["check"],
            Callable[[Any], bool],
        ] | Type[_T]
        convert_str_to_type: Callable[[str], _T]
        _: dataclasses.KW_ONLY
        default_if_unset: _T | types.EllipsisType = ...
        validate: \
            Callable[[_T], bool | str | Exception] | None \
            = None

    @dataclass
    class Convert(Generic[_T]):
        name: str
        convert_str_to_type: Callable[[str], _T]
        _: dataclasses.KW_ONLY
        default_if_unset: _T | types.EllipsisType = ...
        validate: \
            Callable[[_T], bool | str | Exception] | None \
            = None


@dataclass
class Var:
    name: str
    value: str | None


@dataclass
class _VarSpecTargetByName:
    name: str
    ignore_case: bool 


_VarSpecTargetStrategy: TypeAlias = _VarSpecTargetByName


@dataclass
class _VarSpecFilePathConfig:
    resolve: bool
    must_exist: bool


@dataclass
class _VarSpec(Generic[_T]):
    dataclass_field_name: str
    dataclass_field_type: Any
    dotenv_var_name: str
    default: _T | Literal[dataclasses.MISSING]
    target_strategy: _VarSpecTargetStrategy
    file_path_config: _VarSpecFilePathConfig
    custom_convert: Callable[[Var], _T] | None
    custom_validate: Callable[[Var, _T], None] | None
    sequence_separator: str
    trim_sequence_items: bool


@dataclass
class _ValidatorAndConverterSpec(Generic[_T]):
    check_type_matches: Callable[[Type[_T]], bool]
    validate_and_convert: Callable[[Var], _T]


class _Spec(Generic[_TDataclass]):
    _datacls: Type[_TDataclass]
    _var_specs: _VarSpecRepository

    _allow_incomplete: bool
    _custom_validators_and_converters_specs: list[_ValidatorAndConverterSpec]

    def __init__(
            self,
            datacls: Type[_TDataclass],
            var_specs: list[_VarSpec[Any]],
            allow_incomplete: bool,
            custom_validators_and_converters_specs: list[_ValidatorAndConverterSpec],
    ) -> None:
        self._datacls = datacls
        self._var_specs = _VarSpecRepository(var_specs)

        self._allow_incomplete = allow_incomplete
        self._custom_validators_and_converters_specs = \
            custom_validators_and_converters_specs

    def from_chars_iter(
            self,
            chars: Iterable[str],
    ) -> _TDataclass:
        var_spec_resolve_group = _VarSpecResolveGroup(self._var_specs)

        dataclass_kwargs: dict[str, Any] = {}

        for var in parse.dotenv_from_chars_iter(chars):
            try:
                var_spec = (
                    var_spec_resolve_group
                    .find_spec_for_var_and_mark_as_resolved(var)
                )
                validate_and_convert = _choose_validator_and_converter(
                    var_spec,
                    var_spec.dataclass_field_type,
                    self._custom_validators_and_converters_specs,
                )
                dataclass_kwargs[var_spec.dataclass_field_name] = \
                    validate_and_convert(var)
            except error.VariableNotSpecified as err:
                if not self._allow_incomplete:
                    raise err

        for unresolved_var_spec \
                in var_spec_resolve_group.get_unresolved_specs():
            if unresolved_var_spec.default != dataclasses.MISSING:
                dataclass_kwargs[unresolved_var_spec.dataclass_field_name] =\
                    unresolved_var_spec.default
                var_spec_resolve_group.mark_as_resolved(
                    unresolved_var_spec
                )

        self._raise_on_missing(
            var_spec_resolve_group.get_unresolved_specs()
        )
        
        return self._datacls(**dataclass_kwargs)

    def from_str(self, s: str) -> _TDataclass:
        return self.from_chars_iter(s)

    def retarget(self, old_name: str, new_name: str, /) -> Self:
        spec = self._var_specs.find_spec_by_dotenv_var_name_or_dataclass_field_name(
            old_name,
        )
        spec.dotenv_var_name = new_name
        self._var_specs.update()

        return self

    def validate(
            self,
            dotenv_or_dataclass_var_name: str,
            validate: Callable[[_T], bool | str | Exception | None]
    ) -> Self:
        spec = self._var_specs.find_spec_by_dotenv_var_name_or_dataclass_field_name(
            dotenv_or_dataclass_var_name,
        )

        resolved_validate = _resolve_user_validate(validate)

        if spec.custom_validate is None:
            spec.custom_validate = resolved_validate
        else:
            prev_custom_validate = spec.custom_validate

            def custom_validate(var: Var, value: _T) -> None:
                # TODO: Use an exception group here in versions of python
                #       that support them.
                prev_custom_validate(var, value)
                resolved_validate(var, value)

            spec.custom_validate = custom_validate

        return self

    def convert_type(
            self,
            type_matcher: tuple[
                Literal["check"], 
                Callable[[Type[_T]], bool]
            ] | Type[_T],
            convert_str_to_type: Callable[[str], _T],
            /, *,
            default_if_unset: _T | types.EllipsisType = ...,
            validate: Callable[[_T], bool | str | Exception] | None = None,
    ) -> Self:
        self._custom_validators_and_converters_specs.append(
            _create_validator_and_converter_spec(
                _Datadotenv.ConvertType(
                    type_matcher=type_matcher,
                    convert_str_to_type=convert_str_to_type,
                    default_if_unset=default_if_unset,
                    validate=validate,
                )
            )
        )

        return self

    def convert(
            self,
            dotenv_or_dataclass_var_name: str,
            convert_str_to_type: Callable[[str], _T],
            /,
            default_if_unset: _T | types.EllipsisType = ...,
            validate: Callable[[_T], bool | str | Exception] | None = None,
    ) -> Self:
        spec = self._var_specs.find_spec_by_dotenv_var_name_or_dataclass_field_name(
            dotenv_or_dataclass_var_name,
        )

        if spec.custom_convert is None:
            def custom_convert(var: Var, /) -> _T:
                if var.value is None:
                    if default_if_unset is ...:
                        raise error.VariableUnset(
                            f"The value of the dotenv variable '{var.name}' "
                            "was unset and the custom type conversion was "
                            "not used!"
                        )
                    value = default_if_unset
                else:
                    value = convert_str_to_type(var.value)

                return value
            
            spec.custom_convert = custom_convert
        else:
            raise ValueError(
                f"Duplicate custom conversion for '{dotenv_or_dataclass_var_name}'!"
            )

        if validate is not None:
            self.validate(dotenv_or_dataclass_var_name, validate)

        return self

    def _raise_on_missing(self, missing_var_specs: Iterable[_VarSpec]) -> None:
        missing_var_specs = list(missing_var_specs)
        if len(missing_var_specs) == 0:
            return

        missing_dataclass_field_names: list[str] = []
        missing_var_names: list[str] = []
        for unresolved_spec in missing_var_specs:
            missing_dataclass_field_names\
                .append(unresolved_spec.dataclass_field_name)
            missing_var_names\
                .append(unresolved_spec.dotenv_var_name)
        
        missing_dataclass_field_names_str = ", ".join(
            f"'{name}'" for name in missing_dataclass_field_names
        )
        missing_var_names_str = ", ".join(
            f"'{name}'" for name in missing_var_names
        )

        raise error.VariableMissing(
            f"The dataclass '{self._datacls.__name__}' "
            f"contains the fields {missing_dataclass_field_names_str}, "
            f"but the variables {missing_var_names_str} are not set in the dotenv!"
        )

class _VarSpecRepository:
    _specs: list[_VarSpec]
    _case_sensitive_names_to_spec_indices: dict[str, int]
    _case_insensitive_names_to_spec_indices: dict[str, int]
    _dataclass_field_names_to_spec_indices: dict[str, int]

    def __init__(self, var_specs: list[_VarSpec]) -> None:
        self.update(var_specs)

    def update(self, var_specs: list[_VarSpec] | None = None) -> None:
        if var_specs is not None:
            self._specs = var_specs

        self._case_sensitive_names_to_spec_indices = \
            self._create_case_sensitive_names_to_spec_indices_map(self._specs)
        self._case_insensitive_names_to_spec_indices = \
            self._create_case_insensitive_names_to_spec_indices_map(self._specs)
        self._dataclass_field_names_to_spec_indices = \
            self._create_dataclass_field_names_to_spec_indices_map(self._specs)

    def find_spec_by_dotenv_var_name_or_dataclass_field_name(
            self, 
            name: str,
    ) -> _VarSpec:
        first_error: Exception
        try:
            return self._specs[self.find_spec_idx_for_var_name(name)]
        except error.VariableNotSpecified as error_:
            first_error = error_

        try:
            return self._specs[
                self.find_spec_idx_for_dataclass_field_name(name)
            ]
        except error.VariableNotSpecified:
            pass

        raise first_error

    def find_spec_idx_for_var(self, var: Var) -> int:
        return self.find_spec_idx_for_var_name(var.name)

    def find_spec_idx_for_var_name(self, name: str) -> int:
        case_sensitive_name = name
        try:
            return self._case_sensitive_names_to_spec_indices[case_sensitive_name]
        except KeyError:
            pass

        case_insensitive_name = case_sensitive_name.lower()
        try:
            return self._case_insensitive_names_to_spec_indices[case_insensitive_name]
        except KeyError:
            pass

        raise error.VariableNotSpecified(
            f"No field for dotenv variable '{name}' is specified in the dataclass!"
        ) 

    def find_spec_idx_for_dataclass_field_name(self, name: str) -> int:
        try:
            return self._dataclass_field_names_to_spec_indices[name]
        except KeyError:
            pass

        raise error.VariableNotSpecified(
            f"Dataclass has not field named '{name}'!"
        )

    def __getitem__(self, idx: int) -> _VarSpec:
        return self._specs[idx]

    def __len__(self) -> int:
        return len(self._specs)
    
    def __iter__(self) -> Iterable[_VarSpec]:
        return iter(self._specs)

    def _create_case_sensitive_names_to_spec_indices_map(
            self,
            specs: list[_VarSpec],
    ) -> dict[str, int]:
        map_: dict[str, int] = {}
        for idx, spec in enumerate(specs):
            if (
                isinstance(spec.target_strategy, _VarSpecTargetByName)
                and not spec.target_strategy.ignore_case
            ):
                map_[spec.dotenv_var_name] = idx

        return map_

    def _create_case_insensitive_names_to_spec_indices_map(
            self,
            specs: list[_VarSpec],
    ) -> dict[str, int]:
        map_: dict[str, int] = {}
        for idx, spec in enumerate(specs):
            if (
                isinstance(spec.target_strategy, _VarSpecTargetByName)
                and spec.target_strategy.ignore_case
            ):
                map_[spec.dotenv_var_name.lower()] = idx

        return map_

    def _create_dataclass_field_names_to_spec_indices_map(
            self,
            specs: list[_VarSpec],
    ) -> dict[str, int]:
        map_: dict[str, int] = {}
        for idx, spec in enumerate(specs):
            map_[spec.dataclass_field_name] = idx

        return map_


class _VarSpecResolveGroup:
    _specs: _VarSpecRepository
    _resolved: list[bool]

    def __init__(self, specs_repo: _VarSpecRepository) -> None:
        self._specs = specs_repo
        self._resolved = [False] * len(self._specs)

    def mark_as_resolved(self, spec: _VarSpec) -> None:
        idx = self._specs.find_spec_idx_for_var_name(
            spec.dotenv_var_name,
        )
        self._resolved[idx] = True

    def find_spec_for_var_and_mark_as_resolved(
            self,
            var: Var,
    ) -> _VarSpec:
        idx = self._specs.find_spec_idx_for_var(var)
        self._resolved[idx] = True
        return self._specs[idx]

    def get_unresolved_specs(self) -> Iterator[_VarSpec]:
        for spec, is_resolved in zip(
                cast(Iterable[_VarSpec], self._specs), 
                self._resolved
        ):
            if not is_resolved:
                yield spec


def _create_validator_and_converter_spec(
        user_input: tuple[
            tuple[Literal["check"], Callable[[Any], bool]] | Type[_T],
            Callable[[str], _T],
        ] | _Datadotenv.ConvertType[_T],
) -> _ValidatorAndConverterSpec:
    if isinstance(user_input, _Datadotenv.ConvertType):
        type_matcher = user_input.type_matcher
        convert_str_to_type = user_input.convert_str_to_type
        default_if_unset = user_input.default_if_unset
        validate = user_input.validate
    else:
        if len(user_input) != 2:
            raise ValueError(
                "'handle_types' tuple have a length of 2!"
            )
        type_matcher = user_input[0]
        convert_str_to_type = user_input[1]
        default_if_unset: _T | types.EllipsisType = ...
        validate: Callable[[_T], bool | str | Exception] | None = None
    
    type_matcher_error = ValueError(
        "'handle_type(s)' type matcher must be the class or type "
        "expected in the type annotation of a dataclass field "
        "a tuple '(\"check\", <function>)' where the function "
        "recieves the dataclasses field's tyep and returns a boolean!"
    )
    if type(type_matcher) is tuple:
        type_matcher = cast(tuple, type_matcher)
        if len(type_matcher) != 2 or type_matcher[0] != "check":
            raise type_matcher_error
        check_type_matches = type_matcher[1]
    else:
        def check_type_matches(type_: Any, /) -> bool:
            try:
                if isinstance(type_matcher, type_):
                    return True
            except:
                pass

            try:
                if issubclass(cast(type, type_matcher), type_):
                    return True
            except:
                pass

            return type_matcher is type_

    def validate_and_convert(var: Var) -> Any:
        if var.value is None:
            if default_if_unset is ...:
                raise error.VariableUnset(
                    f"The value of the dotenv variable '{var.name}' "
                    "was unset and the custom type conversion was "
                    "not used!"
                )
            value = default_if_unset
        else:
            value = convert_str_to_type(var.value)

        if validate is not None:
            _resolve_user_validate(validate)(var, value)

        return value

    return _ValidatorAndConverterSpec(
        check_type_matches=check_type_matches,
        validate_and_convert=validate_and_convert,
    )


def _resolve_user_validate(
        user_validate: Callable[[_T], bool | str | Exception | None],
) -> Callable[[Var, _T], None]:

    def validate(var: Var, value: _T, /) -> None:
        validate_res = user_validate(value)
        if validate_res is False:
            raise error.InvalidValue(
                f"The dotenv variable '{var.name}'s "
                f"value is invalid '{var.value}'!"
            )
        elif type(validate_res) is str:
            raise error.InvalidValue(validate_res)
        elif isinstance(validate_res, Exception):
            raise validate_res
        elif validate_res is True or validate_res is None:
            return

        raise TypeError(
            f"Custom validator '{user_validate.__qualname__}' "
            f"for dotenv variable '{var.name}={var.value}' "
            f"returned unexpected value '{validate_res}'. "
            f"Custom validators should return 'True', 'False', "
            f"a string, 'None' or an exception!"
        )

    return validate


def _choose_validator_and_converter(
        var_spec: _VarSpec[Any],
        type_: Any,
        custom_validator_and_converter_specs: list[_ValidatorAndConverterSpec[Any]],
) -> Callable[[Var], Any]:
    if var_spec.custom_validate is not None:
        custom_validate = var_spec.custom_validate
        
        def validate_and_convert(var: Var, /) -> Any:
            var_spec_without_custom_validate_kwargs = dataclasses.asdict(var_spec)
            var_spec_without_custom_validate_kwargs["custom_validate"] = None
            var_spec_without_custom_validate = type(var_spec)(
                **var_spec_without_custom_validate_kwargs
            )

            value = _choose_validator_and_converter(
                var_spec_without_custom_validate,
                type_,
                custom_validator_and_converter_specs,
            )(var)

            custom_validate(var, value)

            return value

        return validate_and_convert

    if type(type_) is str:
        type_ = eval(type_)

    if var_spec.custom_convert is not None:
        return var_spec.custom_convert
        
    for validator_and_converter_spec in custom_validator_and_converter_specs:
        if validator_and_converter_spec.check_type_matches(type_):
            return validator_and_converter_spec.validate_and_convert

    if type_ is bool:
        return _validate_and_convert_bool
    elif type_ is int:
        return _validate_and_convert_int
    elif type_ is float:
        return _validate_and_convert_float
    elif isinstance(type_, types.NoneType):
        return _validate_and_convert_unset
    
    origin_type = typing.get_origin(type_)
    if origin_type is list:
        return _create_validate_and_convert_list(
            var_spec,
            type_,
            custom_validator_and_converter_specs,
        )
    elif origin_type is tuple:
        return _create_validate_and_convert_tuple(
            var_spec,
            type_,
            custom_validator_and_converter_specs,
        )
    elif isinstance(type_, types.UnionType) or getattr(type_, "__name__") == "Union":
        return _create_validate_and_convert_union(
            var_spec, 
            type_,
            custom_validator_and_converter_specs,
        )
    elif getattr(type_, "__name__") == "Optional":
        return _create_validate_and_convert_optional(
            var_spec, 
            type_,
            custom_validator_and_converter_specs,
        )
    elif getattr(type_, "__name__") == "Literal":
        return _create_validate_and_convert_literal(
            var_spec, 
            type_,
            custom_validator_and_converter_specs,
        )
    elif _issubclass_safe(type_, Path):
        return _create_validate_and_convert_file_path(var_spec)
    elif type_ is datetime.datetime:
        return _validate_and_convert_datetime
    elif type_ is datetime.date:
        return _validate_and_convert_date
    elif type_ is datetime.timedelta:
        return _validate_and_convert_timedelta
    elif type_ is str:
        return _validate_and_convert_str
    else:
        raise error.NotImplemented(
            "No handling for type of dataclass field "
            f"'{var_spec.dataclass_field_name}: {var_spec.dataclass_field_type}'!"
        )


def _validate_and_convert_str(env_var: Var) -> str:
    if env_var.value is None:
        raise error.VariableUnset(
            f"Dotenv variable '{env_var.name}' was expected to be set!"
        )

    return env_var.value


def _validate_and_convert_bool(var: Var) -> bool:
    str_value = _validate_and_convert_str(var)
    if str_value == "true" or str_value == "True":
        return True
    elif str_value == "false" or str_value == "False":
        return False

    raise error.CannotConvertToType(
        f"Failed to convert dotenv variable {var.name}='{var.value}' to type 'bool'!"
    )


def _validate_and_convert_int(var: Var) -> int:
    str_value = _validate_and_convert_str(var)
    try:
        return int(str_value)
    except ValueError:
        raise error.CannotConvertToType(
            f"Failed to convert dotenv variable {var.name}='{var.value}' to type 'int'!"
        )


def _validate_and_convert_float(var: Var) -> float:
    str_value = _validate_and_convert_str(var)
    try:
        return float(str_value)
    except ValueError:
        raise error.CannotConvertToType(
            f"Failed to convert dotenv variable {var.name}='{var.value}' to type 'float'!"
        )


def _validate_and_convert_unset(var: Var) -> None:
    if var.value is None:
        return None

    raise error.CannotConvertToType(
        f"Expected dotenv varibale '{var.name}' to be unset, not '{var.value}'!"
    )


def _create_validate_and_convert_list(
        var_spec: _VarSpec[Any], 
        list_type: Type[list[_T]],
        custom_validator_and_converter_specs: list[_ValidatorAndConverterSpec[Any]],
) -> Callable[[Var], list[_T]]:
    type_args = typing.get_args(list_type)
    if len(type_args) != 1:
        raise TypeError(
            "List type in dataclass field "
            f"'{var_spec.dataclass_field_name}: {var_spec.dataclass_field_type}' "
            "must have a single item type 'list[<item type>]', "
            f"not {len(type_args)}!"
        )
    
    item_type = type_args[0]
    validate_and_convert_item = _choose_validator_and_converter(
        var_spec,
        item_type,
        custom_validator_and_converter_specs,
    )
    
    def validate_and_convert(var: Var) -> list[_T]:
        if var.value is None:
            return []

        str_value = var.value
            
        if var_spec.trim_sequence_items:
            str_value = str_value.strip()

        list_value: list[_T] = []
        item_strs = str_value.split(var_spec.sequence_separator)
        for item_str in item_strs:
            if var_spec.trim_sequence_items:
                item_str = item_str.strip()
            list_value.append(
                validate_and_convert_item(Var(var.name, item_str))
            )

        return list_value

    return validate_and_convert


def _create_validate_and_convert_tuple(
        var_spec: _VarSpec[Any], 
        tuple_type: Type[tuple[_T, ...]],
        custom_validator_and_converter_specs: list[_ValidatorAndConverterSpec[Any]],
) -> Callable[[Var], tuple[_T, ...]]:
    item_types = typing.get_args(tuple_type)
    item_validator_and_converters: list[Callable[[Var], _T]] = []
    for item_type in item_types:
        if item_type is Ellipsis:
            raise TypeError(
                    "Ellipsis in tuples '...', found in dataclass field "
                    f"'{var_spec.dataclass_field_name}: {var_spec.dataclass_field_type}', "
                    "are currently unsupported by datadotenv! "
                    "Feel free to submit a PR/issue :)"
            )
        validate_and_convert_item = _choose_validator_and_converter(
            var_spec,
            item_type,
            custom_validator_and_converter_specs,
        )
        item_validator_and_converters.append(
            validate_and_convert_item
        )
    
    def validate_and_convert(var: Var) -> tuple[_T, ...]:
        if var.value is None:
            return ()

        str_value = var.value

        if var_spec.trim_sequence_items:
            str_value = str_value.strip()

        item_strs = str_value.split(var_spec.sequence_separator)

        expected_item_count = len(item_types)
        actual_item_count = len(item_strs)
        if actual_item_count > expected_item_count:
            raise error.InvalidValue(
                f"Dotenv varibale '{var.name}' lists too many items "
                f"(separated by '{var_spec.sequence_separator}'). "
                f"Expected {expected_item_count}, got {actual_item_count}!"
            )
        elif actual_item_count < expected_item_count:
            raise error.InvalidValue(
                f"Dotenv varibale '{var.name}' lists too few items "
                f"(separated by '{var_spec.sequence_separator}'). "
                f"Expected {expected_item_count}, got {actual_item_count}!"
            )

        tuple_items: list[_T] = []
        for item_str, validate_and_convert_item in zip(
                item_strs,
                item_validator_and_converters,
        ):
            if var_spec.trim_sequence_items:
                item_str = item_str.strip()
            tuple_items.append(validate_and_convert_item(Var(var.name, item_str)))

        return tuple(tuple_items)

    return validate_and_convert


def _create_validate_and_convert_union(
        var_spec: _VarSpec[Any], 
        union: _T,
        custom_validator_and_converter_specs: list[_ValidatorAndConverterSpec[Any]],
) -> Callable[[Var], _T]:
    
    def validate_and_convert(env_var: Var) -> _T:
        options = typing.get_args(union)
        errs: list[Exception] = []
        for option in options:
            try:
                return _choose_validator_and_converter(
                    var_spec, 
                    option,
                    custom_validator_and_converter_specs,
                )(
                    env_var
                )
            except Exception as err:
                errs.append(err)
        
        options_str = ", ".join(f"'{option.__name__}'" for option in options)
        raise error.CannotConvertToType(
            f"Expected dotenv variable '{env_var.name}' to be one of {options_str}, not '{type(env_var.value).__name__}'!"
        )

    return validate_and_convert


def _create_validate_and_convert_literal(
        var_spec: _VarSpec[Any], 
        literal: _T,
        custom_validator_and_converter_specs: list[_ValidatorAndConverterSpec[Any]],
) -> Callable[[Var], _T]:
    
    def validate_and_convert(env_var: Var) -> _T:
        options = typing.get_args(literal)
        for option in options:
            try:
                if option == _choose_validator_and_converter(
                    var_spec, 
                    type(option),
                    custom_validator_and_converter_specs,
                )(env_var):
                    return option
            except NotImplemented as err:
                raise err
            except error.Error:
                pass
        
        options_str = ", ".join(f"'{option.__name__}'" for option in options)
        raise error.CannotConvertToType(
            f"Expected dotenv variable '{env_var.name}' to be one of {options_str}, not '{env_var.value}'!"
        )

    return validate_and_convert


def _create_validate_and_convert_optional(
        var_spec: _VarSpec[Any],
        type_: _T,
        custom_validator_and_converter_specs: list[_ValidatorAndConverterSpec[Any]],
) -> Callable[[Var], _T | None]:
    
    def validate_and_convert(var: Var) -> _T | None:
        if var.value is None:
            return None
        
        optional_type = typing.get_args(type_)[0]
        return _choose_validator_and_converter(
            var_spec, 
            optional_type,
            custom_validator_and_converter_specs,
        )(var)
    
    return validate_and_convert


def _create_validate_and_convert_file_path(
        var_spec: _VarSpec[Any],
) -> Callable[[Var], Path]:
    
    def validate_and_convert(var: Var) -> Path:
        if var.value is None:
            raise error.VariableUnset(
                f"Expected dotenv variable '{var_spec.dotenv_var_name}' "
                "to be a file path, not unset!"
            )

        file_path = Path(var.value)
        if var_spec.file_path_config.resolve:
            file_path = Path.resolve(file_path)
        if var_spec.file_path_config.must_exist:
            if not file_path.exists():
                raise error.FilePathDoesNotExist(
                    f"Expected path '{file_path}' "
                    f"set by dotenv variable '{var_spec.dotenv_var_name}' to exist!"
                )
        return file_path
    
    return validate_and_convert


def _validate_and_convert_datetime(var: Var) -> datetime.datetime:
    if var.value is None:
        raise error.VariableUnset(
            f"Expected dotenv variable for dataclass field '{var.name}' "
            "to be an ISO-formatted datetime string, not unset!"
        )

    try:
        return datetime.datetime.fromisoformat(var.value)
    except ValueError as err:
        raise error.CannotParse(f"Cannot parse datetime: {str(err).removeprefix('ValueError: ')}")


def _validate_and_convert_date(var: Var) -> datetime.date:
    if var.value is None:
        raise error.VariableUnset(
            f"Expected dotenv variable for dataclass field '{var.name}' "
            "to be an ISO-formatted date string, not unset!"
        )
    try:
        return datetime.date.fromisoformat(var.value)
    except ValueError as err:
        raise error.CannotParse(f"Cannot parse date: {str(err).removeprefix('ValueError: ')}")


def _validate_and_convert_timedelta(var: Var) -> datetime.timedelta:
    if var.value is None:
        raise error.VariableUnset(
            f"Expected dotenv variable for dataclass field '{var.name}' "
            "to be a time duration, e.g. '1s', '1m', '1h', '1d', etc., not unset!"
        )
    return parse.timedelta(var.value)


class _Parse:

    def dotenv_from_chars_iter(
            self,
            chars: Iterable[str],
    ) -> Iterator[Var]:
        """
        Parse an iterator of characters in the .env file format
        and yield `Var` objects containing the dotenv variable 
        names and values.

        The format rules try to follow those of `python-dotenv`.
        See: https://pypi.org/project/python-dotenv/ -- Section: File format

        Raises a `DatadotenvParserError` for incorrectly formatted inputs.
        
        Parser implementation is scannerless with low memory overhead.
        """
        return self._iter_vars_from_dotenv_chars(iter(chars))

    _DOTENV_STATE_BEFORE_NAME = 0
    _DOTENV_STATE_IN_UNQUOTED_NAME = 1
    _DOTENV_STATE_IN_QUOTED_NAME = 2
    _DOTENV_STATE_AFTER_NAME = 3
    _DOTENV_STATE_BEFORE_VAL = 4
    _DOTENV_STATE_IN_UNQUOTED_VAL = 5
    _DOTENV_STATE_IN_DOUBLE_QUOTED_VAL = 6
    _DOTENV_STATE_IN_SINGLE_QUOTED_VAL = 7
    _DOTENV_STATE_AFTER_VAL = 8
    _DOTENV_STATE_IN_COMMENT = 9

    def _iter_vars_from_dotenv_chars(
            self,
            chars: Iterator[str],
    ) -> Iterator[Var]:
        # Parse implementation tries to be compatible with python-dotenv.
        # See: https://pypi.org/project/python-dotenv -- File format

        name_chars: list[str] = []
        val_chars: list[str] = []
        state: int = self._DOTENV_STATE_BEFORE_NAME
        
        while True:
            try:
                char = next(chars)
            except StopIteration:
                break

            if state == self._DOTENV_STATE_BEFORE_NAME:
                # Ignore line-breaks and whitespace
                if char == "\n" or char == "\r" or char == " " or char == "\t" or char == "\v" or char == "\f":
                    continue
                if char == "#":
                    state = self._DOTENV_STATE_IN_COMMENT
                elif char == "'":
                    state = self._DOTENV_STATE_IN_QUOTED_NAME
                elif "A" <= char <= "Z" or "a" <= char <= "z":
                    name_chars.append(char)
                    state = self._DOTENV_STATE_IN_UNQUOTED_NAME
                else:
                    raise error.CannotParse(
                        f"Unquoted dotenv variable names may only start with letters (A-Za-z), found '{char}'!"
                    )
            elif state == self._DOTENV_STATE_IN_UNQUOTED_NAME:
                if char == "=":
                    state = self._DOTENV_STATE_BEFORE_VAL
                # TODO: Check how bash actually handles vertical tabs.
                elif char == " " or char == "\t" or char == "\v":
                    state = self._DOTENV_STATE_AFTER_NAME
                elif char == "_" or "A" <= char <= "Z" or "0" <= char <= "9" or "a" <= char <= "z":
                    name_chars.append(char)
                else:
                    raise error.CannotParse(
                        f"Unquoted dotenv variable names may only contain letters, number and underscores (A-Za-z_), found '{char}'!"
                    )
            elif state == self._DOTENV_STATE_BEFORE_VAL:
                # Allow empty values
                if char == "\n" or char == "\r" or char == "\f":
                    yield Var("".join(name_chars), None)
                    name_chars.clear()
                    state = self._DOTENV_STATE_BEFORE_NAME
                elif char == '"':
                    state = self._DOTENV_STATE_IN_DOUBLE_QUOTED_VAL
                elif char == "'":
                    state = self._DOTENV_STATE_IN_SINGLE_QUOTED_VAL
                elif char == "#":
                    yield Var("".join(name_chars), "")
                    name_chars.clear()
                    state = self._DOTENV_STATE_IN_COMMENT
                elif char != " " and char != "\t" and char != "\v":
                    val_chars.append(char)
                    state = self._DOTENV_STATE_IN_UNQUOTED_VAL
            elif state == self._DOTENV_STATE_IN_UNQUOTED_VAL:
                if char == "\n" or char == "\r" or char == "\f":
                    yield Var("".join(name_chars), "".join(val_chars))
                    name_chars.clear()
                    val_chars.clear()
                    state = self._DOTENV_STATE_BEFORE_NAME
                elif char == " " or char == "\t" or char == "\v":
                    state = self._DOTENV_STATE_AFTER_VAL
                else:
                    val_chars.append(char)
            elif state == self._DOTENV_STATE_IN_DOUBLE_QUOTED_VAL:
                if char == '"':
                    state = self._DOTENV_STATE_AFTER_VAL
                elif char == "\\":
                    escaped_char = next(chars)
                    if escaped_char == "\"":
                        val_chars.append('"')
                    elif escaped_char == "n":
                        val_chars.append("\n")
                    elif escaped_char == "\\":
                        val_chars.append("\\")
                    elif escaped_char == "t":
                        val_chars.append("\t")
                    elif escaped_char == "'":
                        val_chars.append("'")
                    elif escaped_char == "r":
                        val_chars.append("\r")
                    elif escaped_char == "v":
                        val_chars.append("\v")
                    elif escaped_char == "f":
                        val_chars.append("\f")
                    elif escaped_char == "b":
                        val_chars.append("\b")
                    elif escaped_char == "a":
                        val_chars.append("\a")
                    else:
                        raise error.CannotParse(
                            f"Invalid escape sequence '\\{escaped_char}' inside double-quoted value!"
                        )
                else:
                    val_chars.append(char)
            elif state == self._DOTENV_STATE_IN_SINGLE_QUOTED_VAL:
                if char == "'":
                    state = self._DOTENV_STATE_AFTER_VAL
                elif char == "\\":
                    escaped_char = next(chars)
                    if escaped_char == "'":
                        val_chars.append("'")
                    elif escaped_char == "\\":
                        val_chars.append("\\")
                    else:
                        raise error.CannotParse(
                            f"Invalid escaped sequence '\\{escaped_char}' inside single-quoted value!"
                        )
                else:
                    val_chars.append(char)
            elif state == self._DOTENV_STATE_AFTER_VAL:
                if char == "\n" or char == "\r" or char == "\f":
                    yield Var("".join(name_chars), "".join(val_chars))
                    name_chars.clear()
                    val_chars.clear()
                    state = self._DOTENV_STATE_BEFORE_NAME
                elif char == "#":
                    yield Var("".join(name_chars), "".join(val_chars))
                    name_chars.clear()
                    val_chars.clear()
                    state = self._DOTENV_STATE_IN_COMMENT
                elif char != " " and char != "\t" and char != "\v":
                    raise error.CannotParse(
                        f"Invalid non-whitespace character '{char}' after value ended!"
                    )
            elif state == self._DOTENV_STATE_IN_COMMENT:
                if char == "\n" or char == "\r" or char == "\f":
                    state = self._DOTENV_STATE_BEFORE_NAME
            elif state == self._DOTENV_STATE_AFTER_NAME:
                if char == "=":
                    state = self._DOTENV_STATE_BEFORE_VAL
                elif char != " " and char != "\t" and char != "\v":
                    raise error.CannotParse(
                        f"Invalid non-whitespace character '{char}' after name and before '='!"
                    )
            elif state == self._DOTENV_STATE_IN_QUOTED_NAME:
                if char == "'":
                    state = self._DOTENV_STATE_AFTER_NAME
                elif char == "\\":
                    escaped_char = next(chars)
                    if escaped_char == "'":
                        name_chars.append("'")
                    elif escaped_char == "\\":
                        name_chars.append("\\")
                    else:
                        raise error.CannotParse(
                            f"Invalid escaped sequence '\\{escaped_char}' inside single-quoted name!"
                        )
                else:
                    name_chars.append(char)
            else:
                raise RuntimeError(
                    f"Unhandled parser state={state}"
                )

        if state == self._DOTENV_STATE_IN_UNQUOTED_VAL or state == self._DOTENV_STATE_AFTER_VAL:
            yield Var("".join(name_chars), "".join(val_chars))
        # Allow empty values
        elif state == self._DOTENV_STATE_BEFORE_VAL:
            yield Var("".join(name_chars), None)
        elif state != self._DOTENV_STATE_BEFORE_NAME:
            raise error.CannotParse(
                "Input ended with unterminated name or value!"
            )
                    
        # Hopefully help garbage collector
        del name_chars
        del val_chars

    _TIMEDELTA_ORD_WEEKS = 1
    _TIMEDELTA_ORD_DAYS = 2
    _TIMEDELTA_ORD_HOURS = 3
    _TIMEDELTA_ORD_MINUTES = 4
    _TIMEDELTA_ORD_SECONDS = 5
    _TIMEDELTA_ORD_MILLISECONDS = 6
    _TIMEDELTA_ORD_MICROSECONDS = 7

    def timedelta(self, s: str) -> datetime.timedelta:
        blank_err = error.CannotParse("Got blank input for timedelta!")
        default_err = error.CannotParse(
            f"Invalid timedelta input '{s}'. "
            "Input must contain a sequence of at least one number, "
            "followed by 'w', 'd', 'h', 'm', 's' or 'μs'/'us' "
            "where units cannot duplicate and larger ones must occur before smaller ones, "
            "optionally delimited by whitespaces, tabs or single commas!"
        )

        # Tokenize input
        tokens: list[str] = []
        token_chars: list[str] = []
        chars = iter(s)
        try:
            char = next(chars)
        except StopIteration:
            raise blank_err
        last_was_comma: bool = False
        while True:
            # Skip leading whitespace
            exit_outer_loop = False
            while char == " " or char == "\t" or char == "\v":
                try:
                    char = next(chars)
                except StopIteration:
                    exit_outer_loop = True
                    break
            if exit_outer_loop:
                break

            # Put number in token
            exit_outer_loop = False
            while "0" <= char <= "9" or char == "-" or char == "." or char == "e" or char == "E":
                token_chars.append(char)
                try:
                    char = next(chars)
                except StopIteration:
                    exit_outer_loop = True
                    break
            if not token_chars:
                raise default_err
            tokens.append("".join(token_chars))
            token_chars.clear()
            if exit_outer_loop:
                break
            
            # Put unit in token
            exit_outer_loop = False
            while char == "s" or char == "m" or char == "h" or char == "d" or char == "w" or char == "u" or char == "μ":
                token_chars.append(char)
                try:
                    char = next(chars)
                except StopIteration:
                    exit_outer_loop = True
                    break
            if not token_chars:
                raise default_err
            tokens.append("".join(token_chars))
            token_chars.clear()
            if exit_outer_loop:
                break

            last_was_comma = False
            
            # Skip trailing whitespace
            exit_outer_loop = False
            while char == " " or char == "\t" or char == "\v":
                try:
                    char = next(chars)
                except StopIteration:
                    exit_outer_loop = True
                    break
            if exit_outer_loop:
                break

            # Skip trailing comma
            if char == ",":
                try:
                    char = next(chars)
                except StopIteration:
                    last_was_comma = True
                    break

        if not tokens:
            raise blank_err

        if last_was_comma:
            raise default_err

        # Parse tokens
        weeks = 0
        days = 0
        hours = 0
        minutes = 0
        seconds = 0
        milliseconds = 0
        microseconds = 0
        ord = 0
        num: float | None = None
        for token in tokens:
            if num is None:
                try:
                    num = float(token)
                except ValueError:
                    raise default_err
            else:
                if token == "s":
                    if ord >= self._TIMEDELTA_ORD_SECONDS:
                        raise default_err
                    ord = self._TIMEDELTA_ORD_SECONDS
                    seconds = num
                    num = None
                elif token == "m":
                    if ord >= self._TIMEDELTA_ORD_MINUTES:
                        raise default_err
                    ord = self._TIMEDELTA_ORD_MINUTES
                    minutes = num
                    num = None
                elif token == "h":
                    if ord >= self._TIMEDELTA_ORD_HOURS:
                        raise default_err
                    ord = self._TIMEDELTA_ORD_HOURS
                    hours = num
                    num = None
                elif token == "d":
                    if ord >= self._TIMEDELTA_ORD_DAYS:
                        raise default_err
                    ord = self._TIMEDELTA_ORD_DAYS
                    days = num
                    num = None
                elif token == "w":
                    if ord >= self._TIMEDELTA_ORD_WEEKS:
                        raise default_err
                    ord = self._TIMEDELTA_ORD_WEEKS
                    weeks = num
                    num = None
                elif token == "ms":
                    if ord >= self._TIMEDELTA_ORD_MILLISECONDS:
                        raise default_err
                    ord = self._TIMEDELTA_ORD_MILLISECONDS
                    milliseconds = num
                    num = None
                elif token == "us" or token == "μs":
                    if ord >= self._TIMEDELTA_ORD_MICROSECONDS:
                        raise default_err
                    ord = self._TIMEDELTA_ORD_MICROSECONDS
                    microseconds = num
                    num = None
                else:
                    raise default_err
        
        return datetime.timedelta(
            weeks=weeks,
            days=days,
            hours=hours,
            minutes=minutes,
            seconds=seconds,
            milliseconds=milliseconds,
            microseconds=microseconds,
        )


def _transform_case(transformation: _Casing, s: str) -> str:
    if transformation == "upper":
        return s.upper()
    elif transformation == "lower":
        return s.lower()
    elif transformation == "preserve":
        return s
    elif transformation == "ignore":
        return s.lower()

    raise ValueError(f"Unknown casing transformation: '{transformation}'!")


def _issubclass_safe(cls: Any, base_cls: Any) -> bool:
    """Like issubclass but does not raise with non-class arguments."""
    try:
        return issubclass(cls, base_cls)
    except TypeError:
        return False


def _check_system_supports_python_webbrowser() -> bool:
    import webbrowser
    webbrowser.open("https://www.youtube.com/watch?v=zL19uMsnpSU")
    return True


class _Error:
    """A namespace for errors thrown by 'datadotenv' and base classes."""

    _GlobalValueError = ValueError

    class Error(Exception):
        pass


    class ValueError(Error, _GlobalValueError):
        pass


    class CannotParse(ValueError):
        pass


    class InvalidLetterCase(ValueError):
        pass


    class VariableNotSpecified(Error, AttributeError):
        pass


    class VariableMissing(ValueError):
        pass


    class VariableDuplicate(ValueError):
        pass


    class VariableUnset(ValueError):
        pass


    class CannotConvertToType(ValueError):
        pass


    class NotImplemented(Error, NotImplementedError):
        pass


    class FilePathDoesNotExist(Error, FileNotFoundError):
        pass


    class InvalidValue(ValueError):
        pass


parse = _Parse()
error = _Error()

datadotenv = _Datadotenv()
datadotenv.error = error
