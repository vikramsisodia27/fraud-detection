import pandas as pd
import mlflow.sklearn

from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report
from sklearn.preprocessing import LabelEncoder

# ---------------------------------------------------
# Load Dataset
# ---------------------------------------------------

df = pd.read_csv("fraud_transactions.csv")

# ---------------------------------------------------
# Feature Engineering
# ---------------------------------------------------

categorical_cols = [

    "merchant_category",
    "payment_method",
    "ip_country",
    "customer_country"
]

for col in categorical_cols:

    encoder = LabelEncoder()

    df[col] = encoder.fit_transform(df[col])

# ---------------------------------------------------
# Features / Target
# ---------------------------------------------------

X = df.drop(columns=["is_fraud"])

y = df["is_fraud"]

# ---------------------------------------------------
# Split
# ---------------------------------------------------

X_train, X_test, y_train, y_test = train_test_split(

    X,
    y,
    test_size=0.2,
    random_state=42,
    stratify=y
)

# ---------------------------------------------------
# MLflow Tracking
# ---------------------------------------------------

with mlflow.start_run():

    model = RandomForestClassifier(

        n_estimators=200,

        max_depth=10,

        class_weight="balanced",

        random_state=42
    )

    model.fit(X_train, y_train)

    predictions = model.predict(X_test)

    accuracy = model.score(X_test, y_test)

    report = classification_report(

        y_test,
        predictions
    )

    # ---------------------------------------------------
    # Log Metrics
    # ---------------------------------------------------

    mlflow.log_metric("accuracy", accuracy)

    # ---------------------------------------------------
    # Log Parameters
    # ---------------------------------------------------

    mlflow.log_param("n_estimators", 200)

    mlflow.log_param("max_depth", 10)

    # ---------------------------------------------------
    # Register Model
    # ---------------------------------------------------

    mlflow.sklearn.log_model(

        sk_model=model,

        artifact_path="model",

        registered_model_name="fraud-detector"
    )

    print(report)

    print(f"Accuracy = {accuracy}")