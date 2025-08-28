# Contributing

## Making Contributions

Contributions to the APEx Dispatch API are welcome! If you have suggestions for improvements, bug fixes, or new features, please follow these steps:

1. **Fork the repository**: Create a personal copy of the repository on GitHub.
2. **Create a new branch**: Use a descriptive name for your branch that reflects the changes you plan to make.
   ```bash
   git checkout -b feature/your-feature-name
   ```
3. **Make your changes**: Implement the changes you want to contribute.
4. **Write tests**: Ensure that your changes are covered by tests. Add new tests if necessary.
5. **Run tests**: Verify that all tests pass before submitting your changes.
   ```bash
   pytest
   ```
6. **Commit your changes**: Write a clear commit message that describes your changes.
   ```bash
   git commit -m "Add feature: your feature description"
   ```
7. **Push your changes**: Push your branch to your forked repository.
   ```bash
   git push origin feature/your-feature-name
   ```
8. **Create a pull request**: Go to the original repository and create a pull request (PR) from your branch. Provide a clear description of the changes and why they are needed.

## Registration of a new Platform Implementation

To add a new platform implementation, you will need to create a new class that inherits from the `BaseProcessingPlatform` class located at `app/platforms/base.py`. In this new class, you will need to implement all the abstract methods defined in the `BaseProcessingPlatform` class. This will ensure that your new platform implementation adheres to the expected interface and functionality.

To register the new implementation, it is important to add the following directive right above the class definition:

```python
from app.platforms.dispatcher import register_platform
from app.schemas.enum import ProcessTypeEnum

@register_platform(ProcessTypeEnum.OGC_API_PROCESS)
class OGCAPIProcessPlatform(BaseProcessingPlatform):
    ...
```

The processing type, defined by `ProcessTypeEnum`, is the unique identifier for the platform implementation. It is used to distinguish between different platform implementations in the system. This value is used by the different request endpoints to determine which platform implementation to use for processing the request. To add a new platform implementation, you will need to define a new `ProcessTypeEnum` value in the `app/schemas/enum.py` file. This value should be unique and descriptive of the platform you are implementing.

Once you have completed the above steps, the new platform implementation will be registered automatically and made available for use in the APEx Dispatch API. You can then proceed to implement the specific functionality required for your platform.