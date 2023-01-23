#!/usr/bin/env python3
# coding: utf-8

from pathlib import Path
from typing import Any, Dict, Optional

from nii_dg.entity import ContextualEntity
from nii_dg.error import GovernanceError, PropsError
from nii_dg.ro_crate import ROCrate
from nii_dg.schema.base import File as BaseFile
from nii_dg.utils import (access_url, check_all_prop_types,
                          check_content_formats, check_content_size,
                          check_isodate, check_mime_type, check_required_props,
                          check_sha256, check_unexpected_props, check_url,
                          classify_uri, load_entity_def_from_schema_file,
                          sum_file_size, verify_is_past_date)


class DMPMetadata(ContextualEntity):
    def __init__(self, props: Optional[Dict[str, Any]] = None):
        super().__init__(id="#AMED-DMP", props=props)
        self["name"] = "AMED-DMP"

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

        if self.id != "#AMED-DMP":
            raise PropsError(f"The value of @id property of {self} MUST be '#AMED-DMP'.")

        if self["name"] != "AMED-DMP":
            raise PropsError(f"The value of name property of {self} MUST be 'AMED-DMP'.")

        if self.type != self.entity_name:
            raise PropsError(f"The value of @type property of {self} MUST be '{self.entity_name}'.")

    def validate(self, rocrate: ROCrate) -> None:
        organization = self["funder"]
        if "funder" in rocrate.root.keys() and organization not in rocrate.root["funder"]:
            raise GovernanceError(f"The entity {organization} is funder property of {self}, but not included in the list of funder property of RootDataEntity.")

        if len(self["hasPart"]) > 0:
            if "creator" not in self.keys():
                raise GovernanceError(f"A creator property is required in {self}.")
            if "hostingInstitution" not in self.keys():
                raise GovernanceError(f"A hostingInstitution property is required in {self}.")
            if "dataManager" not in self.keys():
                raise GovernanceError(f"A dataManager property is required in {self}.")


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

        if self.id != "#dmp:" + str(self["dataNumber"]):
            raise PropsError(f"The value of @id property of {self} MUST be started with '#dmp:'and then the value of dataNumber property MUST come after it.")

        if self.type != self.entity_name:
            raise PropsError(f"The value of @type property of {self} MUST be '{self.entity_name}'.")

        if verify_is_past_date(self, "availabilityStarts"):
            raise PropsError(f"The value of availabilityStarts property of {self} MUST be the date of future.")

    def validate(self, rocrate: ROCrate) -> None:
        if self["accessRights"] in ["Unshared", "Restricted Closed Sharing"]:
            if not any(map(self.keys().__contains__, ("availabilityStarts", "accessRightsInfo"))):
                raise GovernanceError(
                    f"An availabilityStarts property is required in {self}. If you keep data unshared, ab accessRightsInfo property is required instead.")

        if verify_is_past_date(self, "availabilityStarts"):
            raise GovernanceError(f"The value of availabilityStarts property of {self} MUST be the date of future.")

        if self["gotInformedConsent"] == "yes" and "informedConsentFormat" not in self.keys():
            raise GovernanceError(f"An informedConsentFormat property is required in {self}.")

        dmp_metadata_ents = rocrate.get_by_entity_type(DMPMetadata)
        if len(dmp_metadata_ents) == 0:
            raise GovernanceError("DMPMetadata Entity MUST be required with DMP entity.")
        dmp_metadata_ent = dmp_metadata_ents[0]
        if self not in dmp_metadata_ent["hasPart"]:
            raise GovernanceError(f"DMP entity {self} is not included in the list of hasPart property of {dmp_metadata_ent}.")

        if "repository" not in self.keys():
            # DMPMetadata entity must have the property instead of DMP entity
            if "repository" not in dmp_metadata_ents[0].keys():
                raise GovernanceError(f"A repository property is required in {self}.")

        if self["accessRights"] == "Unrestricted Open Sharing" and "distribution" not in self.keys():
            # DMPMetadata entity must have the property instead of DMP entity
            if "distribution" not in dmp_metadata_ents[0].keys():
                raise GovernanceError(f"A distribution property is required in {self}.")

        if "contentSize" in self.keys():
            sum = sum_file_size(self["contentSize"][-2:], rocrate, File)

            if self["contentSize"] != "over100GB" and sum > int(self["contentSize"]):
                raise GovernanceError(f"The total file size included in DMP {self} is larger than the defined size.")

            if self["contentSize"] == "over100GB" and sum < 100:
                raise GovernanceError(f"The total file size included in DMP {self} is smaller than 100GB.")


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
            raise PropsError(f"The value of @id property of {self} MUST be URL or relative path to the file, not absolute path.")

        check_content_formats(self, {
            "contentSize": check_content_size,
            "encodingFormat": check_mime_type,
            "url": check_url,
            "sha256": check_sha256,
            "sdDatePublished": check_isodate
        })

        if self.type != self.entity_name:
            raise PropsError(f"The value of @type property of {self} MUST be '{self.entity_name}'.")

        if verify_is_past_date(self, "sdDatePublished") is False:
            raise PropsError(f"The value of sdDatePublished property of {self} MUST be the date of past.")

    def validate(self, rocrate: ROCrate) -> None:
        # failures = GovernanceError(self)

        if classify_uri(self, "@id") == "URL":
            if "sdDatePublished" not in self.keys():
                raise GovernanceError(f"A sdDatePublished property MUST be included in {self}.")
                # failures.add("sdDatepublished", "This property MUST be required, but not found.")
        # if len(failures.failure_dict) > 0:
        #     raise failures


class ClinicalResearchRegistration(ContextualEntity):
    def __init__(self, id: str, props: Optional[Dict[str, Any]] = None):
        super().__init__(id=id, props=props)

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
            "@id": check_url,
        })

        if self.type != self.entity_name:
            raise PropsError(f"The value of @type property of {self} MUST be '{self.entity_name}'.")

    def validate(self, rocrate: ROCrate) -> None:
        access_url(self.id)
