#!/usr/bin/env python3
# coding: utf-8

from pathlib import Path
from typing import Any, Dict, Optional

from nii_dg.entity import ContextualEntity
from nii_dg.error import CrateError, EntityError, PropsError
from nii_dg.ro_crate import ROCrate
from nii_dg.schema.base import File as BaseFile
from nii_dg.schema.base import Person as BasePerson
from nii_dg.utils import (access_url, check_all_prop_types,
                          check_content_formats, check_content_size,
                          check_erad_researcher_number, check_isodate,
                          check_mime_type, check_orcid_id,
                          check_required_props, check_sha256,
                          check_unexpected_props, check_url, classify_uri,
                          load_entity_def_from_schema_file, sum_file_size,
                          verify_is_past_date)


class DMPMetadata(ContextualEntity):
    def __init__(self, props: Optional[Dict[str, Any]] = None):
        super().__init__(id="#CAO-DMP", props=props)
        self["name"] = "CAO-DMP"

    @property
    def schema_name(self) -> str:
        return Path(__file__).stem

    @property
    def entity_name(self) -> str:
        return self.__class__.__name__

    def as_jsonld(self) -> Dict[str, Any]:
        self.check_props()
        return super().as_jsonld()

    def check_props(self) -> None:
        entity_def = load_entity_def_from_schema_file(self.schema_name, self.entity_name)

        check_unexpected_props(self, entity_def)
        check_required_props(self, entity_def)
        check_all_prop_types(self, entity_def)

        if self.id != "#CAO-DMP":
            raise PropsError(f"The value of @id property of {self} MUST be '#CAO-DMP'.")

        if self["name"] != "CAO-DMP":
            raise PropsError(f"The value of name property of {self} MUST be 'CAO-DMP'.")

        if self.type != self.entity_name:
            raise PropsError(f"The value of @type property of {self} MUST be '{self.entity_name}'.")

    def validate(self, crate: ROCrate) -> None:
        validation_failures = EntityError(self)

        organization = self["funder"]
        if "funder" in crate.root.keys() and organization not in crate.root["funder"]:
            validation_failures.add("funder", f"The entity {organization} is not included in the funder property of RootDataEntity.")

        if len(self["hasPart"]) != len(crate.get_by_entity_type(DMP)):
            diff = set(self["hasPart"]) ^ set(crate.get_by_entity_type(DMP))
            validation_failures.add("hasPart", f"There is an omission of DMP entity in the list: {diff}.")

        if len(validation_failures.message_dict) > 0:
            raise validation_failures


class DMP(ContextualEntity):
    def __init__(self, id: int, props: Optional[Dict[str, Any]] = None):
        super().__init__(id="#dmp:" + str(id), props=props)
        self["dataNumber"] = id

    @property
    def schema_name(self) -> str:
        return Path(__file__).stem

    @property
    def entity_name(self) -> str:
        return self.__class__.__name__

    def as_jsonld(self) -> Dict[str, Any]:
        self.check_props()
        return super().as_jsonld()

    def check_props(self) -> None:
        entity_def = load_entity_def_from_schema_file(self.schema_name, self.entity_name)

        check_unexpected_props(self, entity_def)
        check_required_props(self, entity_def)
        check_all_prop_types(self, entity_def)

        check_content_formats(self, {
            "availabilityStarts": check_isodate
        })

        if not self.id.startswith("#dmp:"):
            raise PropsError(f"The value of @id property of {self} MUST be started with '#dmp:'.")

        if self.type != self.entity_name:
            raise PropsError(f"The value of @type property of {self} MUST be '{self.entity_name}'.")

        if verify_is_past_date(self, "availabilityStarts"):
            raise PropsError(f"The value of availabilityStarts property in {self} MUST be the date of future.")

    def validate(self, crate: ROCrate) -> None:
        validation_failures = EntityError(self)

        if self["accessRights"] == "embargoed access" and "availabilityStarts" not in self.keys():
            validation_failures.add("availabilityStarts", "This property is required, but not found.")

        if self["accessRights"] in ["open access", "restricted access"] and "isAccessibleForFree" not in self.keys():
            validation_failures.add("isAccessibleForFree", "This property is required, but not found.")

        if self["accessRights"] == "open access" and "license" not in self.keys():
            validation_failures.add("license", "This property is required, but not found.")

        dmp_metadata_ents = crate.get_by_entity_type(DMPMetadata)
        if len(dmp_metadata_ents) == 0:
            raise CrateError("Entity DMPMetadata MUST be required with DMP entity.")
        dmp_metadata_ent = dmp_metadata_ents[0]

        if "repository" not in list(self.keys()) + list(dmp_metadata_ent.keys()):
            validation_failures.add("repository", "This property is required, but not found.")

        if self["accessRights"] == "open access" and "distribution" not in list(self.keys()) + list(dmp_metadata_ent.keys()):
            validation_failures.add("distribution", "This property is required, but not found.")

        if "contentSize" in self.keys():
            sum = sum_file_size(self["contentSize"][-2:], crate, File)

            if self["contentSize"] != "over100GB" and sum > int(self["contentSize"][:-2]):
                validation_failures.add("contentSize", "The total file size included in this DMP is larger than the defined size.")

            if self["contentSize"] == "over100GB" and sum < 100:
                validation_failures.add("contentSize", "The total file size included in this DMP is smaller than 100GB.")

        if len(validation_failures.message_dict) > 0:
            raise validation_failures


class Person(BasePerson):
    def __init__(self, id: str, props: Optional[Dict[str, Any]] = None):
        super().__init__(id=id, props=props)

    @property
    def schema_name(self) -> str:
        return Path(__file__).stem

    @property
    def entity_name(self) -> str:
        return self.__class__.__name__

    def check_props(self) -> None:
        entity_def = load_entity_def_from_schema_file(self.schema_name, self.entity_name)

        check_unexpected_props(self, entity_def)
        check_required_props(self, entity_def)
        check_all_prop_types(self, entity_def)

        check_content_formats(self, {
            "@id": check_url,
            "eradResearcherNumber": check_erad_researcher_number
        })

        if self.id.startswith("https://orcid.org/"):
            check_orcid_id(self.id[18:])

        if self.type != self.entity_name:
            raise PropsError(f"The value of @type property of {self} MUST be '{self.entity_name}'.")

    def validate(self, crate: ROCrate) -> None:
        validation_failures = EntityError(self)

        try:
            access_url(self.id)
        except ValueError as e:
            validation_failures.add("@id", str(e))

        if len(validation_failures.message_dict) > 0:
            raise validation_failures


class File(BaseFile):
    def __init__(self, id: str, props: Optional[Dict[str, Any]] = None):
        super().__init__(id=id, props=props)

    @property
    def schema_name(self) -> str:
        return Path(__file__).stem

    @property
    def entity_name(self) -> str:
        return self.__class__.__name__

    def check_props(self) -> None:
        entity_def = load_entity_def_from_schema_file(self.schema_name, self.entity_name)

        check_unexpected_props(self, entity_def)
        check_required_props(self, entity_def)
        check_all_prop_types(self, entity_def)

        if classify_uri(self, "@id") == "abs_path":
            raise PropsError(f"The @id value in {self} MUST be URL or relative path to the file, not absolute path.")

        check_content_formats(self, {
            "contentSize": check_content_size,
            "encodingFormat": check_mime_type,
            "sha256": check_sha256,
            "url": check_url,
            "sdDatePublished": check_isodate
        })

        if self.type != self.entity_name:
            raise PropsError(f"The value of @type property of {self} MUST be '{self.entity_name}'.")

        if verify_is_past_date(self, "sdDatePublished") is False:
            raise PropsError(f"The value of sdDatePublished property of {self} MUST be the date of past.")

    def validate(self, crate: ROCrate) -> None:
        validation_failures = EntityError(self)

        if "sdDatePublished" not in self.keys():
            validation_failures.add("sdDatePublished", "This property is required, but not found.")

        if len(validation_failures.message_dict) > 0:
            raise validation_failures
