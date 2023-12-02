from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from pathlib import Path
import types
import typing
from typing import Any, Callable, ClassVar, Generic, Iterable, Iterator, Literal, Optional, Protocol, Type, TypeAlias, TypeVar, Union


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
    ) -> _Spec[_TDataclass]:
        
        def placeholder_validate_and_convert(_: Var) -> Any:
            raise RuntimeError(
                f"{_VarSpecSingleton.validate_and_convert.__qualname__} "
                f"must be set by {_mut_var_spec_for_type.__qualname__}!"
            )

        var_specs: list[_VarSpec] = []
        for field in dataclasses.fields(datacls):
            var_spec = _VarSpecSingleton(
                dataclass_field_name=field.name,
                dotenv_var_name=_transform_case(case, field.name),
                default=field.default,
                validate_and_convert=placeholder_validate_and_convert,
                target_strategy=_VarSpecTargetByName(
                    name=_transform_case(case, field.name),
                    ignore_case=case == "ignore",
                ),
                file_path_config=_VarSpecFilePathConfig(
                    resolve=resolve_file_paths,
                    must_exist=file_paths_must_exist,
                )
            )
            _mut_var_spec_for_type(var_spec, field.type)
            var_specs.append(var_spec)

        return _Spec(
            datacls, 
            var_specs,
            allow_incomplete=allow_incomplete,
        )

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


def _mut_var_spec_for_type(var_spec: _VarSpec, type_: Any) -> None:
    var_spec.validate_and_convert = _choose_validator_and_converter(
        var_spec,
        type_,
    )


def _choose_validator_and_converter(
        var_spec: _VarSpec,
        type_: Any,
) -> Callable[[Var], Any]:
    if type(type_) is str:
        type_ = eval(type_)

    if type_ is bool:
        return _validate_and_convert_bool
    elif type_ is int:
        return _validate_and_convert_int
    elif type_ is float:
        return _validate_and_convert_float
    elif isinstance(type_, types.NoneType):
        return _validate_and_convert_unset
    elif isinstance(type_, types.UnionType) or getattr(type_, "__name__") == "Union":
        return _create_validate_and_convert_union(var_spec, type_)
    elif getattr(type_, "__name__") == "Optional":
        return _create_validate_and_convert_optional(var_spec, type_)
    elif getattr(type_, "__name__") == "Literal":
        return _create_validate_and_convert_literal(var_spec, type_)
    elif _issubclass_safe(type_, Path):
        return _create_validate_and_convert_file_path(var_spec)
    elif type_ is str:
        return _validate_and_convert_str
    else:
        raise error.NotImplemented(
            f"No handling for type of dataclass field '{var_spec.dataclass_field_name}: {type_.__name__}'!"
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


def _validate_and_convert_int(var: Var) -> bool:
    str_value = _validate_and_convert_str(var)
    try:
        return int(str_value)
    except ValueError:
        raise error.CannotConvertToType(
            f"Failed to convert dotenv variable {var.name}='{var.value}' to type 'int'!"
        )


def _validate_and_convert_float(var: Var) -> bool:
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


def _create_validate_and_convert_union(
        var_spec: _VarSpec, 
        union: _T
) -> Callable[[Var], _T]:
    
    def validate_and_convert(env_var: Var) -> _T:
        options = typing.get_args(union)
        errs: list[Exception] = []
        for option in options:
            try:
                return _choose_validator_and_converter(var_spec, option)(
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
        var_spec: _VarSpec, 
        literal: _T
) -> Callable[[Var], _T]:
    
    def validate_and_convert(env_var: Var) -> _T:
        options = typing.get_args(literal)
        for option in options:
            try:
                if option == _choose_validator_and_converter(var_spec, type(option))(env_var):
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
        var_spec: _VarSpec,
        type_: _T,
) -> Callable[[Var], _T | None]:
    
    def validate_and_convert(var: Var) -> _T | None:
        if var.value is None:
            return None
        
        optional_type = typing.get_args(type_)[0]
        return _choose_validator_and_converter(var_spec, optional_type)(var)
    
    return validate_and_convert


def _create_validate_and_convert_file_path(
        var_spec: _VarSpec,
) -> Callable[[Var], Path]:
    
    def validate_and_convert(var: Var) -> Path:
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
class _VarSpecBase(Generic[_T]):
    dataclass_field_name: str
    dotenv_var_name: str
    default: _T | Type[dataclasses.MISSING]
    target_strategy: _VarSpecTargetStrategy
    file_path_config: _VarSpecFilePathConfig


@dataclass
class _VarSpecSingleton(_VarSpecBase[_T]):
    validate_and_convert: Callable[[Var], _T]


@dataclass
class _VarSpecAccumulator(_VarSpecBase[_T]):
    validate_and_accumulate: Callable[[_T, Var], _T]


_VarSpec: TypeAlias = _VarSpecSingleton[Any] | _VarSpecAccumulator[Any]


class _Spec(Generic[_TDataclass]):
    _datacls: Type[_TDataclass]
    _var_specs: _VarSpecRepository

    _allow_incomplete: bool

    def __init__(
            self,
            datacls: _TDataclass,
            var_specs: list[_VarSpec],
            allow_incomplete: bool,
    ) -> None:
        self._datacls = datacls
        self._var_specs = _VarSpecRepository(var_specs)

        self._allow_incomplete = allow_incomplete

    def from_chars_iter(
            self,
            chars: Iterable[str],
    ) -> _TDataclass:
        var_spec_resolve_group = _VarSpecResolveGroup(self._var_specs)

        dataclass_kwargs: dict[str, Any] = {}

        for var in iter_vars_from_dotenv_chars(chars):
            try:
                var_spec = (
                    var_spec_resolve_group
                    .find_spec_for_var_and_mark_as_resolved(var)
                )
                dataclass_kwargs[var_spec.dataclass_field_name] = \
                    var_spec.validate_and_convert(var)
            except error.VariableNotSpecified as err:
                if not self._allow_incomplete:
                    raise err

        for unresolved_var_spec \
                in var_spec_resolve_group.get_unresolved_specs():
            if unresolved_var_spec.default != dataclasses.MISSING:
                dataclass_kwargs[unresolved_var_spec.dataclass_field_name] = unresolved_var_spec.default
                var_spec_resolve_group.mark_as_resolved(
                    unresolved_var_spec
                )

        self._raise_on_missing(
            var_spec_resolve_group.get_unresolved_specs()
        )
        
        return self._datacls(**dataclass_kwargs)

    def from_str(self, s: str) -> _TDataclass:
        return self.from_chars_iter(s)

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
    _case_sensitive_names_to_spec_indices = dict[str, int]
    _case_insensitive_names_to_spec_indices = dict[str, int]

    def __init__(self, var_specs: list[_VarSpec]) -> None:
        self.update(var_specs)

    def update(self, var_specs: list[_VarSpec]) -> None:
        self._specs = var_specs
        self._case_sensitive_names_to_spec_indices = \
            self._create_case_sensitive_names_to_spec_indices_map(var_specs)
        self._case_insensitive_names_to_spec_indices = \
            self._create_case_insensitive_names_to_spec_indices_map(var_specs)

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
        for spec, is_resolved in zip(self._specs, self._resolved):
            if not is_resolved:
                yield spec


def iter_vars_from_dotenv_chars(
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
    return _iter_vars_from_dotenv_chars(iter(chars))


_PARSER_STATE_BEFORE_NAME = 0
_PARSER_STATE_IN_UNQUOTED_NAME = 1
_PARSER_STATE_IN_QUOTED_NAME = 2
_PARSER_STATE_AFTER_NAME = 3
_PARSER_STATE_BEFORE_VAL = 4
_PARSER_STATE_IN_UNQUOTED_VAL = 5
_PARSER_STATE_IN_DOUBLE_QUOTED_VAL = 6
_PARSER_STATE_IN_SINGLE_QUOTED_VAL = 7
_PARSER_STATE_AFTER_VAL = 8
_PARSER_STATE_IN_COMMENT = 9


def _iter_vars_from_dotenv_chars(
        chars: Iterator[str],
) -> Iterator[tuple[str, str]]:
    # Parse implementation tries to be compatible with python-dotenv.
    # See: https://pypi.org/project/python-dotenv -- File format

    name_chars: list[str] = []
    val_chars: list[str] = []
    state: int = _PARSER_STATE_BEFORE_NAME
    
    while True:
        try:
            char = next(chars)
        except StopIteration:
            break

        if state == _PARSER_STATE_BEFORE_NAME:
            # Ignore line-breaks and whitespace
            if char == "\n" or char == "\r" or char == " " or char == "\t" or char == "\v" or char == "\f":
                continue
            if char == "#":
                state = _PARSER_STATE_IN_COMMENT
            elif char == "'":
                state = _PARSER_STATE_IN_QUOTED_NAME
            elif "A" <= char <= "Z" or "a" <= char <= "z":
                name_chars.append(char)
                state = _PARSER_STATE_IN_UNQUOTED_NAME
            else:
                raise error.CannotParse(
                    f"Unquoted dotenv variable names may only start with letters (A-Za-z), found '{char}'!"
                )
        elif state == _PARSER_STATE_IN_UNQUOTED_NAME:
            if char == "=":
                state = _PARSER_STATE_BEFORE_VAL
            # TODO: Check how bash actually handles vertical tabs.
            elif char == " " or char == "\t" or char == "\v":
                state = _PARSER_STATE_AFTER_NAME
            elif char == "_" or "A" <= char <= "Z" or "0" <= char <= "9" or "a" <= char <= "z":
                name_chars.append(char)
            else:
                raise error.CannotParse(
                    f"Unquoted dotenv variable names may only contain letters, number and underscores (A-Za-z_), found '{char}'!"
                )
        elif state == _PARSER_STATE_BEFORE_VAL:
            # Allow empty values
            if char == "\n" or char == "\r" or char == "\f":
                yield Var("".join(name_chars), None)
                name_chars.clear()
                state = _PARSER_STATE_BEFORE_NAME
            elif char == '"':
                state = _PARSER_STATE_IN_DOUBLE_QUOTED_VAL
            elif char == "'":
                state = _PARSER_STATE_IN_SINGLE_QUOTED_VAL
            elif char == "#":
                yield Var("".join(name_chars), "")
                name_chars.clear()
                state = _PARSER_STATE_IN_COMMENT
            elif char != " " and char != "\t" and char != "\v":
                val_chars.append(char)
                state = _PARSER_STATE_IN_UNQUOTED_VAL
        elif state == _PARSER_STATE_IN_UNQUOTED_VAL:
            if char == "\n" or char == "\r" or char == "\f":
                yield Var("".join(name_chars), "".join(val_chars))
                name_chars.clear()
                val_chars.clear()
                state = _PARSER_STATE_BEFORE_NAME
            elif char == " " or char == "\t" or char == "\v":
                state = _PARSER_STATE_AFTER_VAL
            else:
                val_chars.append(char)
        elif state == _PARSER_STATE_IN_DOUBLE_QUOTED_VAL:
            if char == '"':
                state = _PARSER_STATE_AFTER_VAL
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
        elif state == _PARSER_STATE_IN_SINGLE_QUOTED_VAL:
            if char == "'":
                state = _PARSER_STATE_AFTER_VAL
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
        elif state == _PARSER_STATE_AFTER_VAL:
            if char == "\n" or char == "\r" or char == "\f":
                yield Var("".join(name_chars), "".join(val_chars))
                name_chars.clear()
                val_chars.clear()
                state = _PARSER_STATE_BEFORE_NAME
            elif char == "#":
                yield Var("".join(name_chars), "".join(val_chars))
                name_chars.clear()
                val_chars.clear()
                state = _PARSER_STATE_IN_COMMENT
            elif char != " " and char != "\t" and char != "\v":
                raise error.CannotParse(
                    f"Invalid non-whitespace character '{char}' after value ended!"
                )
        elif state == _PARSER_STATE_IN_COMMENT:
            if char == "\n" or char == "\r" or char == "\f":
                state = _PARSER_STATE_BEFORE_NAME
        elif state == _PARSER_STATE_AFTER_NAME:
            if char == "=":
                state = _PARSER_STATE_BEFORE_VAL
            elif char != " " and char != "\t" and char != "\v":
                raise error.CannotParse(
                    f"Invalid non-whitespace character '{char}' after name and before '='!"
                )
        elif state == _PARSER_STATE_IN_QUOTED_NAME:
            if char == "'":
                state = _PARSER_STATE_AFTER_NAME
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

    if state == _PARSER_STATE_IN_UNQUOTED_VAL or state == _PARSER_STATE_AFTER_VAL:
        yield Var("".join(name_chars), "".join(val_chars))
    # Allow empty values
    elif state == _PARSER_STATE_BEFORE_VAL:
        yield Var("".join(name_chars), None)
    elif state != _PARSER_STATE_BEFORE_NAME:
        raise error.CannotParse(
            "Input ended with unterminated name or value!"
        )
                
    # Hopefully help garbage collector
    del name_chars
    del val_chars


def _transform_case(transformation: Literal["upper"], s: str) -> str:
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


error = _Error()

datadotenv = _Datadotenv()
datadotenv.error = error
