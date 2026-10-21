"""P5-only launch connection for an already approved trusted process.

The caller supplies reviewed in-memory components, never module names or an
approval/config loader. Its OS command line must retain ``run app_beta.py``
(the actual checkout path); WindowsP5Observer still verifies that at start.
Streamlit executes app_beta.py as __main__ in this same interpreter, so the
registered operator survives while the canonical entrypoint remains intact.
Importing this module neither registers an operator nor launches a server.
"""
from pathlib import Path

from modules.p5_operator import P5Operator, register_operator


def initialize_and_run(*, authority, observer, credentials, checkpoint,
                       approval_reference, scope_config):
    """Compose/register once before Streamlit runs configured_runtime().

    Call only from the approved trusted process, outside the rerun script.
    Authority/source, Windows identity, scope and release are rechecked by
    existing explicit-start/send/output guards. This call issues no permit,
    reads no credential and performs no P5 store setup or repair.
    """
    operator = P5Operator(authority=authority, observer=observer,
        credentials=credentials, checkpoint=checkpoint,
        approval_reference=approval_reference)
    entrypoint = Path(__file__).resolve().parent.parent / 'app_beta.py'
    config = Path(scope_config).resolve()
    # No child interpreter, import hook, UI callback or configurable entrypoint.
    # Keep the listener local and use the port checked by the supplied observer.
    from streamlit.web import bootstrap
    register_operator(operator)
    flags = {'server_address': '127.0.0.1', 'server_port': observer.port,
        'server_headless': True, 'server_fileWatcherType': 'none',
        'server_runOnSave': False, 'browser_gatherUsageStats': False}
    bootstrap.load_config_options(flags)
    bootstrap.run(str(entrypoint), False, ['--p5-config', str(config)], flags)
