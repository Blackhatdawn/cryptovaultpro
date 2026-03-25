#!/usr/bin/env python3
"""
CryptoVault Backend API Testing Suite
Tests all endpoints mentioned in the review request for iteration 32
"""

import requests
import sys
import json
from datetime import datetime
from typing import Dict, Any, List, Tuple

class CryptoVaultAPITester:
    def __init__(self, base_url: str = "https://secure-trading-api.preview.emergentagent.com"):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.session.timeout = 30
        self.tests_run = 0
        self.tests_passed = 0
        self.test_results: List[Dict[str, Any]] = []

    def log_test(self, name: str, success: bool, details: Dict[str, Any] = None):
        """Log test result"""
        self.tests_run += 1
        if success:
            self.tests_passed += 1
        
        result = {
            "test_name": name,
            "success": success,
            "timestamp": datetime.utcnow().isoformat(),
            "details": details or {}
        }
        self.test_results.append(result)
        
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} - {name}")
        if details and not success:
            print(f"    Details: {details}")

    def test_health_endpoints(self):
        """Test health check endpoints"""
        print("\n🔍 Testing Health Endpoints...")
        
        # Test /health/live
        try:
            response = self.session.get(f"{self.base_url}/health/live")
            success = (response.status_code == 200 and 
                      response.json().get("status") == "ok")
            self.log_test(
                "GET /health/live returns {status: ok} with 200",
                success,
                {"status_code": response.status_code, "response": response.json()}
            )
        except Exception as e:
            self.log_test(
                "GET /health/live returns {status: ok} with 200",
                False,
                {"error": str(e)}
            )

        # Test /health/ready
        try:
            response = self.session.get(f"{self.base_url}/health/ready")
            success = response.status_code == 200
            response_data = response.json()
            
            # Check for required checks
            checks = response_data.get("checks", {})
            has_mongodb = "mongodb" in checks
            has_redis = "redis" in checks  
            has_price_stream = "price_stream" in checks
            
            success = success and has_mongodb and has_redis and has_price_stream
            
            self.log_test(
                "GET /health/ready returns mongodb/redis/price_stream checks with 200",
                success,
                {
                    "status_code": response.status_code,
                    "has_mongodb": has_mongodb,
                    "has_redis": has_redis,
                    "has_price_stream": has_price_stream,
                    "checks": list(checks.keys())
                }
            )
        except Exception as e:
            self.log_test(
                "GET /health/ready returns mongodb/redis/price_stream checks with 200",
                False,
                {"error": str(e)}
            )

    def test_admin_endpoints_unauthorized(self):
        """Test admin endpoints return 401 without authentication"""
        print("\n🔍 Testing Admin Endpoints (Unauthorized)...")
        
        admin_endpoints = [
            ("GET", "/api/admin/withdrawals/pending", "GET /api/admin/withdrawals/pending returns 401 without admin auth"),
            ("GET", "/api/admin/withdrawals/stats", "GET /api/admin/withdrawals/stats returns 401 without admin auth"),
        ]
        
        for method, endpoint, test_name in admin_endpoints:
            try:
                if method == "GET":
                    response = self.session.get(f"{self.base_url}{endpoint}")
                else:
                    response = self.session.request(method, f"{self.base_url}{endpoint}")
                
                success = response.status_code == 401
                self.log_test(
                    test_name,
                    success,
                    {"status_code": response.status_code, "endpoint": endpoint}
                )
            except Exception as e:
                self.log_test(
                    test_name,
                    False,
                    {"error": str(e), "endpoint": endpoint}
                )

    def test_wallet_endpoints_unauthorized(self):
        """Test wallet withdrawal endpoints return 401 without authentication"""
        print("\n🔍 Testing Wallet Endpoints (Unauthorized)...")
        
        # Use dummy withdrawal ID for testing
        dummy_withdrawal_id = "test-withdrawal-id-123"
        
        wallet_endpoints = [
            ("POST", f"/api/wallet/withdraw/{dummy_withdrawal_id}/approve", f"POST /api/wallet/withdraw/{{id}}/approve returns 401 without auth"),
            ("POST", f"/api/wallet/withdraw/{dummy_withdrawal_id}/reject", f"POST /api/wallet/withdraw/{{id}}/reject returns 401 without auth"),
        ]
        
        for method, endpoint, test_name in wallet_endpoints:
            try:
                headers = {"Content-Type": "application/json"}
                response = self.session.request(method, f"{self.base_url}{endpoint}", headers=headers)
                success = response.status_code == 401
                self.log_test(
                    test_name,
                    success,
                    {"status_code": response.status_code, "endpoint": endpoint}
                )
            except Exception as e:
                self.log_test(
                    test_name,
                    False,
                    {"error": str(e), "endpoint": endpoint}
                )

    def test_kyc_endpoints_unauthorized(self):
        """Test KYC endpoints return 401 without authentication"""
        print("\n🔍 Testing KYC Endpoints (Unauthorized)...")
        
        try:
            response = self.session.get(f"{self.base_url}/api/kyc/status")
            success = response.status_code == 401
            self.log_test(
                "GET /api/kyc/status returns 401 without auth",
                success,
                {"status_code": response.status_code}
            )
        except Exception as e:
            self.log_test(
                "GET /api/kyc/status returns 401 without auth",
                False,
                {"error": str(e)}
            )

    def test_backend_startup(self):
        """Test that backend starts without errors by checking basic connectivity"""
        print("\n🔍 Testing Backend Startup...")
        
        try:
            # Test basic connectivity with API ping endpoint
            response = self.session.get(f"{self.base_url}/api/ping")
            success = response.status_code == 200
            
            if success:
                data = response.json()
                has_status = data.get("status") == "ok"
                has_message = data.get("message") == "pong"
                has_version = "version" in data
                success = has_status and has_message and has_version
            
            self.log_test(
                "Backend starts without errors - check supervisor logs",
                success,
                {"status_code": response.status_code, "connectivity": "ok", "api_response": data if success else None}
            )
        except Exception as e:
            self.log_test(
                "Backend starts without errors - check supervisor logs",
                False,
                {"error": str(e)}
            )

    def run_all_tests(self):
        """Run all backend tests"""
        print("🚀 Starting CryptoVault Backend API Tests")
        print(f"📍 Testing against: {self.base_url}")
        print("=" * 60)
        
        # Run test suites
        self.test_health_endpoints()
        self.test_admin_endpoints_unauthorized()
        self.test_wallet_endpoints_unauthorized()
        self.test_kyc_endpoints_unauthorized()
        self.test_backend_startup()
        
        # Print summary
        print("\n" + "=" * 60)
        print("📊 TEST SUMMARY")
        print("=" * 60)
        print(f"Tests Run: {self.tests_run}")
        print(f"Tests Passed: {self.tests_passed}")
        print(f"Tests Failed: {self.tests_run - self.tests_passed}")
        print(f"Success Rate: {(self.tests_passed / self.tests_run * 100):.1f}%")
        
        # Save detailed results
        results = {
            "summary": {
                "tests_run": self.tests_run,
                "tests_passed": self.tests_passed,
                "tests_failed": self.tests_run - self.tests_passed,
                "success_rate": round(self.tests_passed / self.tests_run * 100, 1),
                "timestamp": datetime.utcnow().isoformat(),
                "base_url": self.base_url
            },
            "test_results": self.test_results
        }
        
        with open("/app/test_reports/backend_api_test_results.json", "w") as f:
            json.dump(results, f, indent=2)
        
        print(f"\n📄 Detailed results saved to: /app/test_reports/backend_api_test_results.json")
        
        return self.tests_passed == self.tests_run

def main():
    """Main test execution"""
    tester = CryptoVaultAPITester()
    success = tester.run_all_tests()
    
    if success:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print(f"\n⚠️ {tester.tests_run - tester.tests_passed} test(s) failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())