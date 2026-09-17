
from flask import Flask, render_template, request, jsonify
import sqlite3
from datetime import datetime
from pathlib import Path

app = Flask(__name__)

BASE_DIR = Path(__file__).resolve().parent
DATABASE = BASE_DIR / "foodwaste.db"


# ==========================================
# DATABASE CONNECTION
# ==========================================

def get_db_connection():
    conn = sqlite3.connect(str(DATABASE))
    conn.row_factory = sqlite3.Row
    return conn


# ==========================================
# INITIALIZE DATABASE
# ==========================================

def init_db():
    conn = get_db_connection()

    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS waste_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                food_item TEXT NOT NULL,
                quantity REAL NOT NULL,
                waste_type TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)

        conn.commit()
    finally:
        conn.close()


# ==========================================
# JSON ERROR RESPONSE
# ==========================================

def error_response(message, status=400):
    return jsonify({
        "success": False,
        "message": message
    }), status


# ==========================================
# HOME PAGE
# ==========================================

@app.route("/")
def home():
    return render_template("index.html")


# ==========================================
# ADD FOOD WASTE
# ==========================================

@app.route("/add", methods=["POST"])
def add_waste():

    data = request.get_json(silent=True)

    if data is None:
        data = request.form.to_dict()

    if not isinstance(data, dict):
        return error_response("Invalid request data.")

    food_item = str(
        data.get("food_item", "")
    ).strip()

    quantity = data.get("quantity")

    waste_type = str(
        data.get("waste_type", "")
    ).strip()

    if not food_item or quantity is None or not waste_type:
        return error_response(
            "Please enter all details."
        )

    try:
        quantity = float(quantity)

        if quantity <= 0:
            return error_response(
                "Quantity must be greater than zero."
            )

    except (ValueError, TypeError):
        return error_response(
            "Please enter a valid quantity."
        )

    if not quantity < float("inf"):
        return error_response(
            "Please enter a valid quantity."
        )

    if not quantity > float("-inf"):
        return error_response(
            "Please enter a valid quantity."
        )

    created_at = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    conn = get_db_connection()

    try:
        cursor = conn.execute("""
            INSERT INTO waste_records
            (food_item, quantity, waste_type, created_at)
            VALUES (?, ?, ?, ?)
        """, (
            food_item,
            quantity,
            waste_type,
            created_at
        ))

        record_id = cursor.lastrowid
        conn.commit()

    except sqlite3.Error:
        conn.rollback()
        app.logger.exception("Database insert failed")
        return error_response(
            "Could not save the waste record.",
            500
        )

    finally:
        conn.close()

    return jsonify({
        "success": True,
        "message": "Food waste record added successfully!",
        "id": record_id,
        "food_item": food_item,
        "quantity": quantity,
        "waste_type": waste_type,
        "created_at": created_at
    }), 201


# ==========================================
# GET ALL RECORDS
# ==========================================

@app.route("/records", methods=["GET"])
def get_records():

    conn = get_db_connection()

    try:
        records = conn.execute("""
            SELECT *
            FROM waste_records
            ORDER BY id DESC
        """).fetchall()

        return jsonify({
            "success": True,
            "records": [
                dict(row) for row in records
            ]
        })

    finally:
        conn.close()


# ==========================================
# DELETE A RECORD
# ==========================================

@app.route(
    "/delete/<int:record_id>",
    methods=["POST", "DELETE"]
)
def delete_record(record_id):

    conn = get_db_connection()

    try:
        cursor = conn.execute("""
            DELETE FROM waste_records
            WHERE id = ?
        """, (record_id,))

        deleted = cursor.rowcount
        conn.commit()

    except sqlite3.Error:
        conn.rollback()
        app.logger.exception("Delete failed")
        return error_response(
            "Could not delete the record.",
            500
        )

    finally:
        conn.close()

    if deleted == 0:
        return error_response(
            "Record not found.",
            404
        )

    return jsonify({
        "success": True,
        "message": "Record deleted successfully!"
    })


# ==========================================
# DASHBOARD STATISTICS
# ==========================================

@app.route("/stats", methods=["GET"])
def get_stats():

    conn = get_db_connection()

    try:
        result = conn.execute("""
            SELECT
                COALESCE(SUM(quantity), 0) AS total_waste,
                COUNT(*) AS total_records,
                COALESCE(
                    SUM(
                        CASE
                            WHEN LOWER(waste_type) = 'cooked food'
                            THEN quantity
                            ELSE 0
                        END
                    ), 0
                ) AS cooked_waste
            FROM waste_records
        """).fetchone()

        return jsonify({
            "success": True,
            "total_waste": float(result["total_waste"]),
            "total_records": int(result["total_records"]),
            "cooked_waste": float(result["cooked_waste"]),
            "status": "Active"
        })

    finally:
        conn.close()


# ==========================================
# WASTE ANALYTICS
# ==========================================

@app.route("/analytics", methods=["GET"])
def get_analytics():

    conn = get_db_connection()

    try:
        by_type = conn.execute("""
            SELECT
                waste_type,
                SUM(quantity) AS total_quantity
            FROM waste_records
            GROUP BY waste_type
            ORDER BY total_quantity DESC
        """).fetchall()

        by_food = conn.execute("""
            SELECT
                food_item,
                SUM(quantity) AS total_quantity
            FROM waste_records
            GROUP BY food_item
            ORDER BY total_quantity DESC
        """).fetchall()

        return jsonify({
            "success": True,
            "by_type": [
                dict(row) for row in by_type
            ],
            "by_food": [
                dict(row) for row in by_food
            ]
        })

    finally:
        conn.close()


# ==========================================
# WASTE PREDICTION
# ==========================================

@app.route("/prediction", methods=["GET"])
def get_prediction():

    conn = get_db_connection()

    try:
        result = conn.execute("""
            SELECT
                COUNT(*) AS total_records,
                COALESCE(SUM(quantity), 0) AS total_quantity
            FROM waste_records
        """).fetchone()

        total_records = int(result["total_records"])
        total_quantity = float(result["total_quantity"])

        if total_records == 0:
            predicted = 0
        else:
            predicted = round(
                total_quantity / total_records, 2
            )

        return jsonify({
            "success": True,
            "total_records": total_records,
            "total_waste": total_quantity,
            "predicted_waste": predicted,
            "message": (
                "Prediction is based on the average "
                "quantity per recorded entry."
            )
        })

    finally:
        conn.close()


# ==========================================
# SMART RECOMMENDATIONS
# ==========================================

@app.route("/recommendations", methods=["GET"])
def get_recommendations():

    conn = get_db_connection()

    try:
        result = conn.execute("""
            SELECT
                food_item,
                SUM(quantity) AS total_quantity
            FROM waste_records
            GROUP BY food_item
            ORDER BY total_quantity DESC
            LIMIT 5
        """).fetchall()

        recommendations = []

        if not result:
            recommendations.append(
                "Add food waste records to receive "
                "personalized recommendations."
            )

        else:
            for row in result:
                recommendations.append(
                    "Review preparation and portion sizes "
                    "for " + row["food_item"] + "."
                )

            recommendations.append(
                "Track daily food waste and adjust "
                "food preparation quantities."
            )

        return jsonify({
            "success": True,
            "recommendations": recommendations
        })

    finally:
        conn.close()


# ==========================================
# REFRESH RECORDS
# ==========================================

@app.route("/refresh", methods=["GET"])
def refresh_records():
    return get_records()


# ==========================================
# JSON 404 ERROR
# ==========================================

@app.errorhandler(404)
def not_found(error):
    if request.path.startswith("/api/"):
        return error_response("API endpoint not found.", 404)

    return error_response("Page not found.", 404)


# ==========================================
# JSON 500 ERROR
# ==========================================

@app.errorhandler(500)
def internal_error(error):
    app.logger.exception("Internal server error")
    return error_response(
        "An internal server error occurred.",
        500
    )


# ==========================================
# START APPLICATION
# ==========================================

if __name__ == "__main__":
    init_db()

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True
    )