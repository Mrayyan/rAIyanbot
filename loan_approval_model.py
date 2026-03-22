#!/usr/bin/env python3
"""
Loan Approval Prediction Model
==============================

Final model for predicting loan approval based on applicant features.
Best performance achieved with Decision Tree using engineered features.
"""

import pandas as pd
import numpy as np
from sklearn.tree import DecisionTreeClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, classification_report
import joblib

def create_engineered_features(df):
    """Create additional features to improve model performance"""
    df_eng = df.copy()
    
    # Derived financial ratios
    df_eng['income_to_loan_ratio'] = df_eng['income'] / df_eng['loan_amount']
    df_eng['credit_income_interaction'] = df_eng['credit_score'] * df_eng['income'] / 100000
    df_eng['debt_to_income'] = df_eng['loan_amount'] / df_eng['income']
    
    # Binary indicators
    df_eng['high_credit'] = (df_eng['credit_score'] >= 650).astype(int)
    df_eng['high_income'] = (df_eng['income'] >= 50000).astype(int)
    df_eng['experienced'] = (df_eng['age'] >= 35).astype(int)
    
    return df_eng

def train_final_model():
    """Train and return the final loan approval model"""
    
    # Load data
    df = pd.read_csv('sample_data.csv')
    
    # Engineer features
    df_eng = create_engineered_features(df)
    X = df_eng.drop('approved', axis=1)
    y = df_eng['approved']
    
    # Split data
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.3, random_state=42, stratify=y
    )
    
    # Train final model
    model = DecisionTreeClassifier(random_state=42, max_depth=3)
    model.fit(X_train, y_train)
    
    # Evaluate
    y_pred = model.predict(X_test)
    
    # Print results
    print("Final Model Performance:")
    print(f"Accuracy: {accuracy_score(y_test, y_pred):.3f}")
    print(f"Precision: {precision_score(y_test, y_pred):.3f}")
    print(f"Recall: {recall_score(y_test, y_pred):.3f}")
    print(f"F1-Score: {f1_score(y_test, y_pred):.3f}")
    
    print(f"\nFeature importance:")
    feature_importance = pd.DataFrame({
        'feature': X.columns,
        'importance': model.feature_importances_
    }).sort_values('importance', ascending=False)
    print(feature_importance.head(8))
    
    return model, X.columns

def predict_loan_approval(model, feature_columns, age, income, education_years, 
                         credit_score, loan_amount):
    """Make a loan approval prediction for new applicant"""
    
    # Create input dataframe
    input_data = pd.DataFrame({
        'age': [age],
        'income': [income], 
        'education_years': [education_years],
        'credit_score': [credit_score],
        'loan_amount': [loan_amount]
    })
    
    # Engineer features
    input_eng = create_engineered_features(input_data)
    
    # Ensure all features are present
    for col in feature_columns:
        if col not in input_eng.columns:
            input_eng[col] = 0
    
    # Select features in correct order
    X_input = input_eng[feature_columns]
    
    # Make prediction
    prediction = model.predict(X_input)[0]
    probability = model.predict_proba(X_input)[0]
    
    return prediction, probability

if __name__ == "__main__":
    # Train and save model
    final_model, feature_cols = train_final_model()
    
    # Save model
    joblib.dump((final_model, feature_cols), 'loan_approval_model.pkl')
    print(f"\nModel saved to 'loan_approval_model.pkl'")
    
    # Example prediction
    print(f"\nExample prediction:")
    pred, prob = predict_loan_approval(
        final_model, feature_cols,
        age=30, income=60000, education_years=16, 
        credit_score=700, loan_amount=15000
    )
    print(f"Prediction: {'Approved' if pred == 1 else 'Rejected'}")
    print(f"Probability: {prob[1]:.3f} (approval)")