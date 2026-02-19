import os
import urllib.parse
import requests
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    jsonify,
)

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "change-me-in-production")

ALGOAN_BASE_URL = "https://api.preprod.algoan.com"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_token(username: str, password: str):
    """Exchange credentials for an Algoan access token."""
    url = f"{ALGOAN_BASE_URL}/v1/oauth/token"
    payload = (
        "grant_type=" + urllib.parse.quote("password")
        + "&client_id=" + urllib.parse.quote("console-webapp")
        + "&username=" + urllib.parse.quote(username)
        + "&password=" + urllib.parse.quote(password)
    )
    resp = requests.post(
        url,
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=15,
    )
    return resp


def _signup(access_token: str):
    """Create an organisation and return its id."""
    url = f"{ALGOAN_BASE_URL}/v2/organizations/signup"
    resp = requests.post(
        url,
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=15,
    )
    return resp


def _get_organization(access_token: str, org_id: str):
    """Fetch the organisation record."""
    url = f"{ALGOAN_BASE_URL}/v2/organizations/{org_id}"
    resp = requests.get(
        url,
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=15,
    )
    return resp


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not username or not password:
            return render_template("login.html", error="Please enter your credentials.")

        try:
            resp = _get_token(username, password)
        except requests.RequestException as exc:
            return render_template("login.html", error=f"Network error: {exc}")

        if resp.status_code == 200:
            data = resp.json()
            session["access_token"] = data.get("access_token")
            session["username"] = username
            session["password"] = password
            return redirect(url_for("welcome"))
        else:
            return render_template(
                "login.html",
                error="Invalid username or password. Please try again.",
            )

    return render_template("login.html")


@app.route("/welcome")
def welcome():
    if "access_token" not in session:
        return redirect(url_for("login"))
    return render_template("welcome.html")


@app.route("/start", methods=["POST"])
def start():
    if "access_token" not in session:
        return redirect(url_for("login"))

    access_token = session["access_token"]

    try:
        resp = _signup(access_token)
    except requests.RequestException as exc:
        return render_template("welcome.html", error=f"Network error: {exc}")

    if resp.status_code in (200, 201):
        data = resp.json()
        # The field name may vary; try common keys
        org_id = (
            data.get("id")
            or data.get("organizationId")
            or data.get("_id")
        )
        if not org_id:
            return render_template(
                "welcome.html",
                error="Signup succeeded but could not retrieve organisation ID.",
            )
        session["organization_id"] = org_id
        return redirect(url_for("processing"))
    else:
        return render_template(
            "welcome.html",
            error=f"Signup failed ({resp.status_code}). Please try again.",
        )


@app.route("/processing")
def processing():
    if "access_token" not in session or "organization_id" not in session:
        return redirect(url_for("login"))
    return render_template("processing.html")


@app.route("/api/check-payment-link")
def check_payment_link():
    """Polled by the frontend every few seconds."""
    if "access_token" not in session or "organization_id" not in session:
        return jsonify({"error": "Not authenticated"}), 401

    org_id = session["organization_id"]

    # Re-fetch a fresh token before calling the organization endpoint to avoid
    # 403 errors caused by an expired session token.
    try:
        token_resp = _get_token(session["username"], session["password"])
    except requests.RequestException as exc:
        return jsonify({"error": f"Token refresh failed: {exc}"}), 502

    if token_resp.status_code != 200:
        return jsonify({"error": "Token refresh failed", "status": token_resp.status_code}), 502

    access_token = token_resp.json().get("access_token")
    session["access_token"] = access_token

    try:
        resp = _get_organization(access_token, org_id)
    except requests.RequestException as exc:
        return jsonify({"error": str(exc)}), 502

    if resp.status_code == 200:
        data = resp.json()
        invoice_params = data.get("invoiceParameters") or {}
        payment_link = invoice_params.get("paymentProviderLink")
        if payment_link:
            return jsonify({"status": "ready", "link": payment_link})
        return jsonify({"status": "pending"})

    return jsonify({"error": f"API error {resp.status_code}"}), 502


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
