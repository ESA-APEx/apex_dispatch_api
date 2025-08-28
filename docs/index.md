# APEx Dispatch API

Welcome to the **APEx Dispatch API documentation**!

The APEx Dispatch API is a powerful service designed to execute and upscale Earth Observation (EO) services using [APEx-compliant](https://esa-apex.github.io/apex_documentation/propagation/service_development.html) technologies. It provides a unified interface for running EO-based services across various cloud platforms, regardless of the underlying infrastructure.

## Key Capabilities
The API currently supports the execution of the following types of EO services:

* **openEO-based services**: These are workflows built using the openEO standard.
* **OGC API Processes**: Services that conform to the OGC API Processes standard.

In addition to executing individual services, the APEx Dispatch API also supports upscaling operations. This means that large areas of interest can be automatically divided into smaller, manageable chunks, each processed as a separate job. The API handles the orchestration and coordination of these jobs, simplifying the management of complex and large-scale processing tasks.