# DB Facace

DB Facade is a database obfuscation layer that seeks to achieve the following properties:
* Ensure that the names of descriptive elements in the database are obscured, which makes analysis more difficult
* Minimizes "friction" for developers by, in a development environment, mapping the obscured names back to the semantically meaningful names.
* Separates the database from the mapping layer
* Supports data encryption in production environments

## Basics

To use this package requires several things:

* A modern python version (3.13 or more recent)
* Pydantic data classes
* At least two separate databases:
  - One for the mapping layer
  - One for the data
* A mechanism for managing secrets separate from the database layer

## Design

The design here is that obfuscated data classes are automatically constructed from a
base class library on top of pydantic.
* Data classes can use semantically meaningful names
* class elements are mapped to semantically meaningless UUIDs automatically
* label<->UUID mapping is maintained by a separate regsitry service
  - In development builds, the database layer may map the UUID back to the semantic label
  - In production builds, the database layer remains mapped
* Data objects may be encrypted
  - If encryption is enabled, data keys will be computed from a master key combined with the UUID and/or semantic label.
  - Data elements are always encoded automatically to include:
    * A description of the encoding
    * A description of the encryption algorithm
    * Note: "description" here would imply another UUID instead of a semantically meaningful label
* All outward facing information will show the UUID based labels
  - Exception: development environments
  - Example: database schema
* Any semantically meaningful data must be hidden
  - Example: examples of using the data class must be obfuscated
  - Example: schema definitions containing a description field must be removed or obfuscated (e.g., encrypted)
