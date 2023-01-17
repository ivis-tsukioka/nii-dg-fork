#!/usr/bin/env python3
# coding: utf-8

import ast
import sys
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

import yaml

SCRIPT_TEMPLATE = """\
#!/usr/bin/env python3
# coding: utf-8

import pytest  # noqa: F401
"""

IMPORT_TEMPLATE = """
from nii_dg.schema.{schema_name} import {entity_name}
"""

COMMON_METHODS = """\n
def test_init() -> None:
    ent = {entity_name}({id})
    assert ent["@id"] == "{id_example}"
    assert ent["@type"] == "{entity_type}"
    assert ent.schema_name == "{schema_name}"
    assert ent.entity_name == "{entity_name}"


def test_as_jsonld() -> None:
    ent = {entity_name}({id})
{set_properties}

    jsonld = {sample_ent_json}

    ent_in_json = ent.as_jsonld()
    del ent_in_json["@context"]{rootdataentity_option}
    assert ent_in_json == jsonld


def test_check_props() -> None:
    # TO BE UPDATED
    pass


def test_validate() -> None:
    # TO BE UPDATED
    pass
"""


def add_example_value(
        obj: Dict[str, Any], entity_list: List[str], set_properties: str, import_entities: Set[str], import_entities_from_base: Set[str], child_id: Any = None) -> Tuple[str, Set[str], Set[str]]:
    if obj["expected_type"] == "str" or obj["expected_type"].startswith("Literal"):
        set_properties += "\"{value}\"".format(
            value=obj["example"]
        )
    elif obj["expected_type"] == "bool":
        set_properties += "{value}".format(
            value=obj["example"]
        )
    elif obj["expected_type"].startswith("List["):
        obj["expected_type"] = obj["expected_type"][5:-1]

        obj["example"] = ast.literal_eval(obj["example"])
        if len(obj["example"]) == 1:
            obj["example"] = obj["example"][0]

        set_properties += "["
        set_properties, import_entities, import_entities_from_base = add_example_value(
            obj, entity_list, set_properties, import_entities, import_entities_from_base)
        set_properties += "]"

    elif obj["expected_type"].startswith("Optional["):
        obj["expected_type"] = obj["expected_type"][9:-1]
        set_properties, import_entities, import_entities_from_base = add_example_value(
            obj, entity_list, set_properties, import_entities, import_entities_from_base)

    elif obj["expected_type"].startswith("Union["):
        type_list = obj["expected_type"][6:-1].replace(" ", "").split(",")

        if isinstance(obj["example"], list):
            for i, type_str in enumerate(type_list):
                if i > 0:
                    set_properties += ", "
                obj["expected_type"] = type_str
                child_id = obj["example"][i]

                set_properties, import_entities, import_entities_from_base = add_example_value(
                    obj, entity_list, set_properties, import_entities, import_entities_from_base, child_id)

        elif obj["example"].startswith("{"):
            obj["expected_type"] = type_list[0]
            set_properties, import_entities, import_entities_from_base = add_example_value(
                obj, entity_list, set_properties, import_entities, import_entities_from_base)

        else:
            raise ValueError("Only entity type can be used with Union. Example MUST be the dict of @id property.")

    elif child_id is None and isinstance(obj["example"], list):
        for i, ex in enumerate(obj["example"]):
            if i > 0:
                set_properties += ", "
            child_id = ex
            set_properties, import_entities, import_entities_from_base = add_example_value(
                obj, entity_list, set_properties, import_entities, import_entities_from_base, child_id)

    else:
        if child_id is None and isinstance(obj["example"], str):
            child_id = ast.literal_eval(obj["example"])
        elif child_id is None:
            child_id = obj["example"]
        child_id_str = "\"" + child_id["@id"] + "\""

        if obj["expected_type"] in ["RootDataEntity", "DMPMetadata"]:
            child_id_str = {}
        elif obj["expected_type"] in ["DMP", "GinMonitoring"]:
            child_id_str = int(child_id_str.replace("#dmp:", "").replace("\"", ""))

        set_properties += "{Entity}({id})".format(
            Entity=obj["expected_type"],
            id=child_id_str
        )

        if obj["expected_type"] in entity_list:
            import_entities.add(obj["expected_type"])
        else:
            import_entities_from_base.add(obj["expected_type"])

    return set_properties, import_entities, import_entities_from_base


def main(args: List[str]) -> None:
    schema_file = Path(args[1]).resolve()
    if not schema_file.exists():
        raise FileNotFoundError(f"Schema file {schema_file} does not exist")
    with schema_file.open("r", encoding="utf-8") as f:
        schema = yaml.safe_load(f)
    schema_name = schema_file.stem
    for entity_name, entity in schema.items():
        import_entities = {entity_name}
        import_entities_from_base: Set[str] = set()
        sample_ent_json = {"@type": entity_name}
        set_properties = ""

        for prop_name, obj in entity["props"].items():

            if obj["example"].startswith(("{", "[")) or obj["expected_type"] == "bool":
                sample_ent_json[prop_name] = ast.literal_eval(obj["example"])
            else:
                sample_ent_json[prop_name] = obj["example"]

            if prop_name == "@id":
                continue
            if prop_name == "hasPart" and entity_name == "RootDataEntity":
                continue

            set_properties += f"\n    ent[\"{prop_name}\"] = "

            set_properties, import_entities, import_entities_from_base = add_example_value(
                obj, schema.keys(), set_properties, import_entities, import_entities_from_base)

        scripts = SCRIPT_TEMPLATE + IMPORT_TEMPLATE.format(
            schema_name=schema_name,
            entity_name=", ".join(import_entities)
        )

        if len(import_entities_from_base) > 0:
            scripts += IMPORT_TEMPLATE.format(
                schema_name="base",
                entity_name=", ".join(import_entities_from_base)
            )

        empty_dict: Dict[Any, Any] = {}
        entity_type = entity_name
        entity_id = "\"" + sample_ent_json["@id"] + "\""
        rootdataentity_option = "\n"

        if entity_name == "RootDataEntity":
            sample_ent_json["@type"] = "Dataset"
            entity_type = "Dataset"
            entity_id = empty_dict
            rootdataentity_option = ', ent_in_json["dateCreated"], ent_in_json["hasPart"]\n'

        elif entity_name == "DMPMetadata":
            entity_id = empty_dict
        elif entity_name in ["DMP", "GinMonitoring"]:
            start = sample_ent_json["@id"].find(":") + 1
            entity_id = sample_ent_json["@id"][start:]
        else:
            pass

        scripts += COMMON_METHODS.format(
            entity_name=entity_name,
            entity_type=entity_type,
            schema_name=schema_name,
            id=entity_id,
            id_example=sample_ent_json["@id"],
            set_properties=set_properties,
            sample_ent_json=sample_ent_json,
            rootdataentity_option=rootdataentity_option)

        test_file_dir_path = Path(str((Path(__file__).resolve()).parent) + "/" + schema_name).resolve()
        if test_file_dir_path.exists() is False:
            test_file_dir_path.mkdir()

        test_file_path = Path(str(test_file_dir_path) + "/test_" + entity_name + ".py").resolve()

        with test_file_path.open("w", encoding="utf-8") as f:
            f.write(scripts.strip() + "\n")


if __name__ == "__main__":
    main(sys.argv)