"""GEP callback URLs hosted by the existing APEx Dispatcher."""

CALLBACK_PREFIX = "/integrations/ogc-api-processes/gep/callbacks"


def build_subscriber(base_url: str) -> dict[str, str]:
    prefix = f"{base_url.rstrip('/')}{CALLBACK_PREFIX}"
    return {
        "successUri": f"{prefix}/success",
        "inProgressUri": f"{prefix}/inProgress",
        "failedUri": f"{prefix}/failed",
    }
