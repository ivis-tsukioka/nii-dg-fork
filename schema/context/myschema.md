# NII-DG: Schema: myschema

See [GitHub - NII-DG/nii-dg - schema/README.md](https://github.com/NII-DG/nii-dg/blob/main/schema/README.md) for more information.

## MySchema
A test schema.

| Property | Type | Required? | Description | Example |
| --- | --- | --- | --- | --- |
| `@id` | `str` | Required. | MUST be either a URI Path relative to the RO-Crate root (as stated in the identifier property of RootDataEntity) or an absolute URI. MUST end with `/`. This indicates the path to the directory. | `config` |
| `name` | `str` | Required. | Denotes the directory name. | `config` |
| `url` | `str` | Optional. | MUST be a direct URL link to the directory. | `https://github.com/username/repository/directory` |
| `message` | `str` | Optional. | MUST be a string. | `this is a test message.` |
| `dataId` | `int` | Required. | ID of DATA. Must more than 10 | `1234` |
