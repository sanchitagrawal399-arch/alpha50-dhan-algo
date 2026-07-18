==> Exited with status 1
==> Common ways to troubleshoot your deploy: https://render.com/docs/troubleshooting-deploys
==> Running 'python dhan_cloud_paper.py'
==> Deploying...
==> Setting WEB_CONCURRENCY=1 by default, based on available CPUs in the instance
    dhan = dhanhq(client_id=CLIENT_ID, access_token=ACCESS_TOKEN)
TypeError: dhanhq.__init__() got an unexpected keyword argument 'client_id'
During handling of the above exception, another exception occurred:
Traceback (most recent call last):
  File "/opt/render/project/src/dhan_cloud_paper.py", line 47, in <module>
    dhan = dhanhq()
TypeError: dhanhq.__init__() missing 1 required positional argument: 'dhan_context'
==> Exited with status 1
==> Common ways to troubleshoot your deploy: https://render.com/docs/troubleshooting-deploys
==> Running 'python dhan_cloud_paper.py'
==> Deploying...
==> Setting WEB_CONCURRENCY=1 by default, based on available CPUs in the instance
==> Running 'python dhan_cloud_paper.py'
Traceback (most recent call last):
  File "/opt/render/project/src/dhan_cloud_paper.py", line 40, in <module>
    dhan = dhanhq(dhan_context={"client_id": CLIENT_ID, "access_token": ACCESS_TOKEN})
  File "/opt/render/project/src/.venv/lib/python3.14/site-packages/dhanhq/dhanhq.py", line 58, in __init__
    parent.__init__(self,dhan_context)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/opt/render/project/src/.venv/lib/python3.14/site-packages/dhanhq/_order.py", line 5, in __init__
    self.dhan_http = dhan_context.get_dhan_http()
                     ^^^^^^^^^^^^^^^^^^^^^^^^^^
AttributeError: 'dict' object has no attribute 'get_dhan_http'
==> Exited with status 1
==> Common ways to troubleshoot your deploy: https://render.com/docs/troubleshooting-deploys
==> Running 'python dhan_cloud_paper.py'
==> Deploying...
==> Setting WEB_CONCURRENCY=1 by default, based on available CPUs in the instance
==> Running 'python dhan_cloud_paper.py'
Traceback (most recent call last):
  File "/opt/render/project/src/dhan_cloud_paper.py", line 40, in <module>
    dhan = dhanhq(dhan_context={"client_id": CLIENT_ID, "access_token": ACCESS_TOKEN})
  File "/opt/render/project/src/.venv/lib/python3.14/site-packages/dhanhq/dhanhq.py", line 58, in __init__
    parent.__init__(self,dhan_context)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/opt/render/project/src/.venv/lib/python3.14/site-packages/dhanhq/_order.py", line 5, in __init__
    self.dhan_http = dhan_context.get_dhan_http()
                     ^^^^^^^^^^^^^^^^^^^^^^^^^^
AttributeError: 'dict' object has no attribute 'get_dhan_http'
==> Exited with status 1
==> Common ways to troubleshoot your deploy: https://render.com/docs/troubleshooting-deploys
