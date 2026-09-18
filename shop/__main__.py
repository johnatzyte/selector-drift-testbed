import os

from .app import create_app
from .auth import HEADER

PORT = int(os.environ.get("PORT", "8811"))
HOST = os.environ.get("HOST", "0.0.0.0")

CURLS = """
  curl -s {base}/api/selectors | jq .changed

  curl -s -X PATCH {base}/api/selectors \\
    -H "{header}: $SHOP_API_KEY" \\
    -H 'content-type: application/json' \\
    -d '{{"title_class": "item-name"}}'

  curl -s -X POST {base}/api/selectors/reset -H "{header}: $SHOP_API_KEY"
"""


def main():
    app = create_app()
    base = f"http://localhost:{PORT}"
    print(f"\n  {app.jinja_env.globals['site_name']} on {base}  (dev server)\n")
    print("  Break it with:")
    print(CURLS.format(base=base, header=HEADER))
    # Reloader off on purpose: it would restart the process and wipe the in-memory
    # selector config mid-demo.
    app.run(host=HOST, port=PORT, debug=False, use_reloader=False, threaded=True)


if __name__ == "__main__":
    main()
