#!/usr/bin/env python3
# coding: utf-8

import json

from nii_dg.ro_crate import ROCrate
from nii_dg.schema.base import HostingInstitution, RepositoryObject
from nii_dg.schema.cao import DMP, DMPMetadata, File, Person


def main() -> None:
    ro_crate = ROCrate()
    ro_crate.root["name"] = "example research project"

    org = HostingInstitution("https://www.nii.ac.jp/",
                             {"name": "National Institute of Informatics", "address": "Tokyo Japan"})
    creator = Person("https://ja.wikipedia.org/wiki/%E3%82%A4%E3%83%81%E3%83%AD%E3%83%BC",
                     {"name": "Ichiro Suzuki", "affiliation": org, "email": "ichiro@example.com"})
    repo = RepositoryObject("https://example.com/repository", {"name": "sample repository"})

    dmp_1 = DMP("#dmp:1", {
        "dataNumber": 1,
        "name": "execution results",
        "description": "Files generated by execution of workflow.",
        "creator": [creator],
        "keyword": "Informatics",
        "accessRights": "metadata only access",
        "repository": repo,
        "hostingInstitution": org,
        "dataManager": creator})

    dmp_meta = DMPMetadata(props={
        "about": ro_crate.root,
        "funder": org,
        "keyword": "Informatics",
        "hasPart": [dmp_1]})

    file_cao = File("file_1.txt",
                    {"name": "Sample File", "contentSize": "156GB", "dmpDataNumber": dmp_1})

    ro_crate.add(org, creator, repo, dmp_1, dmp_meta, file_cao)

    print(json.dumps(ro_crate.as_jsonld(), indent=2))


if __name__ == "__main__":
    main()
