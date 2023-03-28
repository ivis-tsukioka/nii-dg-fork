#!/usr/bin/env python3
# coding: utf-8

"""\
Implementation of the RO-Crate class.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from nii_dg.const import RO_CRATE_CONTEXT
from nii_dg.entity import (ContextualEntity, DataEntity, DefaultEntity, Entity,
                           ROCrateMetadata, RootDataEntity)
from nii_dg.error import (CrateCheckPropsError, CrateError,
                          CrateValidationError, EntityError)
from nii_dg.utils import import_custom_class, parse_ctx


class ROCrate():
    """\
    Class representing a Research Object Crate (RO-Crate).

    A RO-Crate is a packaging format for research data that aims to make it easier to share and reuse.

    The class provides methods for adding and removing entities, as well as for dumping the RO-Crate to a file.

    The entities are divided into three types:

    - DefaultEntity: An entity that is always included in the RO-Crate, e.g., ROCrateMetadata, RootDataEntity.
    - DataEntity: An entity that represents a file or directory, e.g., File, Dataset.
    - ContextualEntity: An entity that represents metadata, e.g., Person, License.

    Each entity inherits from the Entity class and is defined in entity.py.

    For more details on the RO-Crate specification, please refer to https://www.researchobject.org/ro-crate/.

    Attributes:
        default_entities (List[DefaultEntity]): A list of default entities.
        data_entities (List[DataEntity]): A list of data entities.
        contextual_entities (List[ContextualEntity]): A list of contextual entities.
        root (RootDataEntity): The root data entity.
    """

    default_entities: List[DefaultEntity]
    data_entities: List[DataEntity]
    contextual_entities: List[ContextualEntity]
    root: RootDataEntity

    def __init__(self, jsonld: Optional[Dict[str, Any]] = None) -> None:
        """\
        Adds entities to the ROCrate.

        Args:
            *entities (Entity): The entities to be added to the ROCrate.

        Raises:
            TypeError: If the entity type is not supported.
        """
        if jsonld is not None:
            self.from_jsonld(jsonld)
        else:
            self.root = RootDataEntity()
            self.default_entities = [self.root, ROCrateMetadata()]
            self.data_entities = []
            self.contextual_entities = []

        self.root["hasPart"] = self.data_entities

    def add(self, *entities: Entity) -> None:
        """\
        Add entities to the RO-Crate.

        Args:
            *entities (Entity): The entities to be added to the RO-Crate.

        Note:
            There are three types of entities that can be added: DefaultEntity, DataEntity, and ContextualEntity.
            If an unsupported entity is given, a TypeError is raised.
        """
        for entity in entities:
            if isinstance(entity, DefaultEntity):
                self.default_entities.append(entity)
            elif isinstance(entity, DataEntity):
                self.data_entities.append(entity)
            elif isinstance(entity, ContextualEntity):
                self.contextual_entities.append(entity)
            else:
                raise TypeError("'Entity' class is not supported to be added directly. Please use 'DefaultEntity', 'DataEntity', or 'ContextualEntity' instead.")

    def remove(self, *entities: Entity) -> None:
        """\
        Removes entities from the ROCrate.

        Args:
            *entities (Entity): The entities to be removed from the ROCrate.

        Raises:
            ValueError: If the entity is not included in the ROCrate or is a DefaultEntity.
            TypeError: If the entity type is not supported.

        Note:
            There are three types of entities that can be removed: DefaultEntity, DataEntity, and ContextualEntity.
            If an unsupported entity is given, a TypeError is raised.
            If the entity is not included in the RO-Crate, a ValueError is raised.
        """
        for entity in entities:
            if entity not in self.all_entities:
                raise ValueError(f"Entity {entity} is not included in the RO-Crate.")

            if isinstance(entity, DefaultEntity):
                raise ValueError(f"Entity {entity} is a DefaultEntity and cannot be removed.")
            elif isinstance(entity, DataEntity):
                self.data_entities.remove(entity)
            elif isinstance(entity, ContextualEntity):
                self.contextual_entities.remove(entity)
            else:
                raise TypeError("'Entity' class is not supported to be removed directly. Please use 'DefaultEntity', 'DataEntity', or 'ContextualEntity' instead.")

    @ property
    def all_entities(self) -> List[Entity]:
        """\
        Get all entities in the RO-Crate.

        Returns:
            List[Entity]: A list of all entities in the RO-Crate.
        """
        return self.default_entities + self.data_entities + self.contextual_entities  # type: ignore

    def get_by_id(self, id_: str) -> List[Entity]:
        """\
        Get entities by ID.

        Args:
            id_ (str): The ID of the entity.

        Returns:
            List[Entity]: A list of entities with the specified ID.
        """
        return [entity for entity in self.all_entities if entity.id == id_]

    def get_by_type(self, type_: str) -> List[Entity]:
        """\
        Get entities by type.

        Args:
            type_ (str): The type of the entity.

        Returns:
            List[Entity]: A list of entities with the specified type.
        """
        return [entity for entity in self.all_entities if entity.type == type_]

    def from_jsonld(self, jsonld: Dict[str, Any]) -> None:
        if not isinstance(jsonld, dict):
            raise TypeError("The JSON-LD data must be a dictionary.")
        if "@context" not in jsonld:
            raise ValueError("The JSON-LD data must have a '@context' key.")
        if jsonld["@context"] != RO_CRATE_CONTEXT:
            raise ValueError("The JSON-LD data must have the RO-Crate context.")
        if "@graph" not in jsonld:
            raise ValueError("The JSON-LD data must have a '@graph' key.")

        root_data_entity = None
        metadata_entity = None
        self.default_entities = []
        self.data_entities = []
        self.contextual_entities = []
        for entity in jsonld["@graph"]:
            id_ = entity.get("@id")
            if id_ is None:
                raise ValueError("The JSON-LD data must have an '@id' key for each entity.")
            type_ = entity.get("@type")
            if type_ is None:
                raise ValueError("The JSON-LD data must have an '@type' key for each entity.")

            if id_ == "./" and type_ == "Dataset":
                root_data_entity = RootDataEntity.from_jsonld(entity)  # type: ignore
            elif id_ == "ro-crate-metadata.json" and type_ == "CreativeWork":
                metadata_entity = ROCrateMetadata.from_jsonld(entity)
            else:
                ctx = entity.get("@context", RO_CRATE_CONTEXT)
                gh_repo, gh_ref, schema = parse_ctx(ctx)
                # TODO impl for other repo
                entity_class = import_custom_class(f"nii_dg.schema.{schema}", type_)
                if entity_class is None:
                    raise ValueError(f"Entity type {type_} is not found.")
                entity_instance = entity_class.from_jsonld(entity)
                if isinstance(entity_instance, DataEntity):
                    self.data_entities.append(entity_instance)
                elif isinstance(entity_instance, ContextualEntity):
                    self.contextual_entities.append(entity_instance)
                else:
                    raise ValueError(f"Entity type {type_} is not supported.")

        if root_data_entity is None:
            raise ValueError("The JSON-LD data must have a root data entity.")
        if metadata_entity is None:
            raise ValueError("The JSON-LD data must have a metadata entity.")

        self.root = root_data_entity  # type: ignore
        self.default_entities = [self.root, metadata_entity]  # type: ignore

    def as_jsonld(self) -> Dict[str, Any]:
        self.check_duplicate_entity()
        self.check_props()

        return {
            "@context": RO_CRATE_CONTEXT,
            "@graph": [entity.as_jsonld() for entity in self.all_entities]
        }

    def dump(self, path: str) -> None:
        """\
        Dump the RO-Crate to the specified path.

        Args:
            path (str): The path to dump the RO-Crate.
        """
        with Path(path).resolve().open("w", encoding="utf-8") as f:
            json.dump(self.as_jsonld(), f, indent=2)

    def check_duplicate_entity(self) -> None:
        """\
        Check for duplicate entities in the RO-Crate.

        Duplicate entities, that is, entities with the same '@id' value, are allowed in the JSON-LD specification.
        For example, a 'File' entity in the 'base' context and a 'File' entity in the 'amed' context can have the same '@id' value.
        This is because the 'name' property in each context is treated as a different property.
        However, if two entities have the same '@id' value and '@context' value, and both have 'name' property with different values, it becomes unclear which one is correct.
        Therefore, this case ('@id' and '@context' are same) is considered as an error and an exception is raised.
        """
        id_ctx = [(entity.id, entity.context) for entity in self.all_entities]
        dup_id_ctx = [id_ctx[i] for i in range(len(id_ctx)) if id_ctx.count(id_ctx[i]) > 1]
        if len(dup_id_ctx) > 0:
            raise CrateError(f"Duplicate entities are found in the RO-Crate: {dup_id_ctx}")

    def check_props(self) -> None:
        crate_error = CrateCheckPropsError()
        for entity in self.all_entities:
            try:
                entity.check_props()
            except EntityError as e:
                crate_error.add(e)
            except Exception as e:
                raise e

        if crate_error.has_error():
            raise crate_error

    def validate(self) -> None:
        crate_error = CrateValidationError()
        for entity in self.all_entities:
            try:
                entity.validate(self)
            except EntityError as e:
                crate_error.add(e)
            except Exception as e:
                raise e

        if crate_error.has_error():
            raise crate_error
