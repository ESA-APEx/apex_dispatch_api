# Contributing to the APEx Dispatch API

## Registration of a new platform implementation

To add a new platform implementation, you will need to create a new class that inherits from the `BasePlatform` class located at [`app/platforms/base.py`](app/platforms/base.py). In this new class, you will need to implement all the abstract methods defined in the [`BasePlatform`](app/platforms/base.py) class. This will ensure that your new platform implementation adheres to the expected interface and functionality.

To register the new implementation, it is important to add the following directive right above the class definition:

```python
from app.platforms.dispatcher import register_platform
from app.schemas.enum import ProcessTypeEnum

@register_platform(ProcessTypeEnum.OGC_API_PROCESS)
```

The processing type is the unique identifier for the platform implementation. It is used to distinguish between different platform implementations in the system. This value is used by the different request endpoints to determine which platform implementation to use for processing the request. To add a new platform implementation, you will need to define a new `ProcessTypeEnum` value in the [`app/schemas/enum.py`](app/schemas/enum.py) file. This value should be unique and descriptive of the platform you are implementing.

Once you have completed the above steps, the new platform implementation will be registered automatically and made available for use in the APEx Dispatch API. You can then proceed to implement the specific functionality required for your platform.