#!/usr/bin/env python3
# coding: utf-8

import datetime
import importlib
import mimetypes
import re
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import (TYPE_CHECKING, Any, Callable, Dict, List, Literal, NewType,
                    Optional, TypedDict, Union)
from urllib.parse import quote, urlparse

import requests
import yaml
from typeguard import check_type as ori_check_type

from nii_dg.error import (GovernanceError, PropsError,
                          UnexpectedImplementationError)

if TYPE_CHECKING:
    from nii_dg.entity import Entity


def github_repo() -> str:
    # TODO use environment variable, git command, or const value (where?)
    return "ascade/nii_dg"


def github_branch() -> str:
    # TODO use environment variable, git command, or const value (where?)
    return "develop"


class EntityDefDict(TypedDict):
    expected_type: str
    required: bool


EntityDef = NewType("EntityDef", Dict[str, EntityDefDict])


def load_entity_def_from_schema_file(schema_name: str, entity_name: str) -> EntityDef:
    schema_file = Path(__file__).resolve().parent.joinpath(f"schema/{schema_name}.yml")
    if not schema_file.exists():
        raise PropsError(f"Tried to load {entity_name} from schema/{schema_name}.yml, but this file is not found.")
    with schema_file.open(mode="r", encoding="utf-8") as f:
        schema_obj = yaml.safe_load(f)
    if entity_name not in schema_obj:
        raise PropsError(f"Tried to load {entity_name} from schema/{schema_name}.yml, but this entity is not found.")

    entity_def: EntityDef = {}  # type: ignore
    for p_name, p_obj in schema_obj[entity_name]["props"].items():
        entity_def[p_name] = {
            "expected_type": p_obj["expected_type"],
            "required": p_obj["required"] == "Required."
        }

    return entity_def


def import_entity_class(schema_name: str, entity_name: str) -> Any:
    """\
    Import entity class from schema module.
    e.g., import_entity_class("base", "RootDataEntity") ->

    from nii_dg.schema.base import RootDataEntity
    return RootDataEntity
    """
    schema_file = Path(__file__).resolve().parent.joinpath(f"schema/{schema_name}.py")
    if not schema_file.exists():
        raise PropsError(f"Tried to import {entity_name} from schema/{schema_name}.py, but this file is not found.")
    module_name = f"nii_dg.schema.{schema_name}"
    module = importlib.import_module(module_name)
    try:
        return getattr(module, entity_name)
    except AttributeError:
        raise PropsError(f"Tried to import {entity_name} from schema/{schema_name}.py, but this entity is not found.") from None


def convert_string_type_to_python_type(type_str: str, schema_name: Optional[str] = None) -> Any:
    """\
    Convert string type to python type.
    e.g. "List[Union[str, int]]" -> List[Union[str, int]]
    """
    if type_str == "bool":
        return bool
    elif type_str == "str":
        return str
    elif type_str == "int":
        return int
    elif type_str == "float":
        return float
    elif type_str == "Any":
        return Any
    elif type_str.startswith("List["):
        return List[convert_string_type_to_python_type(type_str[5:-1], schema_name)]  # type: ignore
    elif type_str.startswith("Union["):
        child_types = tuple([convert_string_type_to_python_type(t, schema_name) for t in type_str[6:-1].split(", ")])
        return Union[child_types]  # type: ignore
    elif type_str.startswith("Optional["):
        return Optional[convert_string_type_to_python_type(type_str[5:-1], schema_name)]
    elif type_str.startswith("Literal["):
        child_list = [t.strip('"').strip("'") for t in type_str[8:-1].split(", ")]
        return Literal[tuple(child_list)]  # type: ignore
    else:
        if "[" in type_str:
            raise PropsError(f"Unexpected type: {type_str}")
        else:
            # Entity subclass in schema module
            schema_name = schema_name or "base"
            entity_class = None
            try:
                entity_class = import_entity_class(schema_name, type_str)
            except PropsError:
                if schema_name != "base":
                    try:
                        entity_class = import_entity_class("base", type_str)
                    except PropsError:
                        pass
            if entity_class is None:
                raise PropsError(f"Unexpected type: {type_str}")
            else:
                return entity_class


def check_prop_type(entity: "Entity", prop: str, value: Any, expected_type: str) -> None:
    """
    Check the type of each property by referring schema.yml.
    """
    excepted_python_type = convert_string_type_to_python_type(expected_type, entity.schema_name)
    try:
        ori_check_type(prop, value, excepted_python_type)
    except TypeError as e:
        ori_msg = str(e)
        base_msg = ori_msg[:ori_msg.find("must be")]
        type_msg = ori_msg[ori_msg.find("must be") + 8:]
        raise PropsError(f"The {base_msg.strip()} in {entity} MUST be {type_msg}.") from None
    except Exception as e:
        raise UnexpectedImplementationError(e)


def check_all_prop_types(entity: "Entity", entity_def: EntityDef) -> None:
    """
    Check the type of all property in the entity by referring schema.yml.
    Called after check_unexpected_props().
    """
    for prop, prop_def in entity_def.items():
        if prop in entity:
            check_prop_type(entity, prop, entity[prop], prop_def["expected_type"])


def check_unexpected_props(entity: "Entity", entity_def: EntityDef) -> None:
    for actual_prop in entity.keys():
        if actual_prop not in entity_def:
            if actual_prop.startswith("@"):
                continue
            raise PropsError(f"Unexpected property: {actual_prop} in {entity}")


def check_required_props(entity: "Entity", entity_def: EntityDef) -> None:
    """
    Check required prop is existing or not.
    If not, raise PropsError.
    """
    required_props = [k for k, v in entity_def.items() if v["required"]]
    for prop in required_props:
        if prop not in entity.keys():
            raise PropsError(f"The term {prop} is required in {entity}.")


def check_content_formats(entity: "Entity", format_rules: Dict[str, Callable[[str], None]]) -> None:
    # TODO 名前もイケてない
    """\
    expected as called after check_required_props(), check_all_prop_types(), check_unexpected_props()
    """
    for prop, check_method in format_rules.items():
        if prop in entity:
            try:
                check_method(entity[prop])
            except (TypeError, ValueError):
                raise PropsError(f"The term {prop} in {entity} is invalid format.") from None
        else:
            # Because optional field
            pass


def classify_uri(entity: "Entity", key: str) -> str:
    """
    Check the value is URI.
    Return 'URL' when the value starts with 'http' or 'https'
    When it is not URL, return 'abs_path' or 'rel_path.
    """
    try:
        encoded_uri = quote(entity[key], safe="!#$&'()*+,/:;=?@[]\\")
        parsed = urlparse(encoded_uri)
    except (TypeError, ValueError):
        raise PropsError(f"The term {key} in {entity} is invalid URI.") from None

    if parsed.scheme in ["http", "https"] and parsed.netloc != "":
        return "URL"
    if PurePosixPath(encoded_uri).is_absolute() or PureWindowsPath(encoded_uri).is_absolute() or parsed.scheme == "file":
        return "abs_path"
    return "rel_path"


def check_url(value: str) -> None:
    """
    Check the value is URL.
    If not, raise ValueError.
    """
    encoded_url = quote(value, safe="!#$&'()*+,/:;=?@[]\\")
    parsed = urlparse(encoded_url)

    if parsed.scheme not in ["http", "https"]:
        raise ValueError
    if parsed.netloc == "":
        raise ValueError


def check_content_size(value: str) -> None:
    """
    Check file size value is in the defined format.
    If not, raise ValueError.
    """
    pattern = r"^\d+[KMGTP]?B$"
    size_match = re.compile(pattern)

    if size_match.fullmatch(value) is None:
        raise ValueError


def check_mime_type(value: str) -> None:
    """
    Check encoding format value is in MIME type format.
    """
    # TODO: mimetypeの辞書がOSによって差分があるのをどう吸収するか, 例えばtext/markdown

    if mimetypes.guess_extension(value) is None:
        raise ValueError


def check_sha256(value: str) -> None:
    """
    Check sha256 value is in SHA256 format.
    """
    pattern = r"(?:[^a-fA-F\d]|\b)([a-fA-F\d]{64})(?:[^a-fA-F\d]|\b)"
    sha_match = re.compile(pattern)

    if sha_match.fullmatch(value) is None:
        raise ValueError


def check_isodate(value: str) -> None:
    """
    Check date is in ISO 8601 format "YYYY-MM-DD".
    """
    datetime.date.fromisoformat(value)


def check_email(value: str) -> None:
    """
    Check email format.
    """
    pattern = r"^[\w\-_]+(.[\w\-_]+)*@([\w][\w\-]*[\w]\.)+[A-Za-z]{2,}$"
    email_match = re.compile(pattern)

    if email_match.fullmatch(value) is None:
        raise ValueError


def check_phonenumber(value: str) -> None:
    """
    Check phone-number format.
    """
    pattern = r"(^0(\d{1}\-?\d{4}|\d{2}\-?\d{3}|\d{3}\-?\d{2}|\d{4}\-?\d{1})\-?\d{4}$|^0[5789]0\-?\d{4}\-?\d{4}$)"
    phone_match = re.compile(pattern)

    if phone_match.fullmatch(value) is None:
        raise ValueError


def check_erad_researcher_number(value: str) -> None:
    """
    Confirm check digit
    """
    if len(value) != 8:
        raise ValueError

    check_digit = int(value[0])
    sum_val = 0
    for i, num in enumerate(value):
        if i == 0:
            continue
        if i % 2 == 0:
            sum_val += int(num) * 2
        else:
            sum_val += int(num)

    if (sum_val % 10) != check_digit:
        raise ValueError


def check_orcid_id(value: str) -> None:
    """
    Check orcid id format and checksum.
    """
    pattern = r"^(\d{4}-){3}\d{3}[\dX]$"
    orcidid_match = re.compile(pattern)

    if orcidid_match.fullmatch(value) is None:
        raise PropsError(f"Orcid ID {value} is invalid.")

    if value[-1] == "X":
        checksum = 10
    else:
        checksum = int(value[-1])
    sum_val = 0
    for num in value.replace("-", "")[:-1]:
        sum_val = (sum_val + int(num)) * 2
    if (12 - (sum_val % 11)) % 11 != checksum:
        raise PropsError(f"Orcid ID {value} is invalid.")


def verify_is_past_date(entity: "Entity", key: str) -> Optional[bool]:
    """
    Check the date is past or not.
    """
    try:
        iso_date = datetime.date.fromisoformat(entity[key])
    except KeyError:
        return None
    except ValueError:
        raise PropsError(f"The value of {key} in {entity} is invalid date format. MUST be 'YYYY-MM-DD'.") from None

    today = datetime.date.today()
    if (today - iso_date).days < 0:
        return False
    return True


def access_url(url: str) -> None:
    """
    Check the url is accessible.
    """
    try:
        res = requests.get(url, timeout=(10.0, 30.0))
        res.raise_for_status()
    except requests.HTTPError as httperr:
        msg = str(httperr)
        raise GovernanceError(f"URL is not accessible. {msg}") from None
    except Exception as err:
        raise UnexpectedImplementationError from err


def get_name_from_ror(ror_id: str) -> List[str]:
    """
    Get organization name from ror.
    """
    api_url = "https://api.ror.org/organizations/" + ror_id

    try:
        res = requests.get(api_url, timeout=(10.0, 30.0))
        res.raise_for_status()
    except requests.HTTPError as httperr:
        if res.status_code == 404:
            raise GovernanceError(f"ROR ID {ror_id} does not exist.") from None
        raise UnexpectedImplementationError from httperr
    except Exception as err:
        raise UnexpectedImplementationError from err

    body = res.json()
    name_list: List[str] = body["aliases"]
    name_list.append(body["name"])
    return name_list