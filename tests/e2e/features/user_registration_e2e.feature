Feature: Complete user registration flow with real email delivery

  # ========================================================================
  # HAPPY PATH SCENARIOS
  # ========================================================================

  Scenario: Successful registration and activation with email verification
    When I register with email "e2e@test.com" and password "SecurePass123"
    Then the response status code should be 201
    And the response should contain user id
    And the user should not be activated
    And an email should be received within 15 seconds
    And the email should contain a 4-digit activation code
    When I activate the account with the code from email
    Then the response status code should be 200
    And the activation should be successful

  Scenario: Complete flow with email code extraction
    Given I register a new user "complete@test.com" with password "MySecurePass123"
    When I wait for the activation email
    And I extract the activation code from the email
    And I activate with the extracted code and correct credentials
    Then the activation should succeed
    And the user should be activated in the system

  # ========================================================================
  # FAILURE SCENARIOS - Test error handling across full system
  # ========================================================================

  Scenario: Activation fails with incorrect code
    Given I register a new user "wrong-code@test.com" with password "SecurePass123"
    When I wait for the activation email
    And I extract the activation code from the email
    And I activate with code "9999" and correct credentials
    Then the response status code should be 400
    And the error should indicate "InvalidActivationCode"
    And the user should not be activated in the system

  Scenario: Already activated user cannot activate again
    Given I register a new user "double-activate@test.com" with password "SecurePass123"
    When I wait for the activation email
    And I extract the activation code from the email
    And I activate with the extracted code and correct credentials
    Then the activation should succeed
    When I try to activate again with the same code
    Then the response status code should be 409
    And the error should indicate "UserAlreadyActivated"

  Scenario: Activation fails with wrong password
    Given I register a new user "wrong-pass@test.com" with password "CorrectPass123"
    When I wait for the activation email
    And I extract the activation code from the email
    And I activate with the code and password "WrongPass123"
    Then the response status code should be 401
    And the user should not be activated in the system

  Scenario: Duplicate email registration is rejected
    Given I register a new user "duplicate@test.com" with password "FirstPass123"
    When I wait for the activation email
    When I try to register again with "duplicate@test.com" and password "SecondPass123"
    Then the response status code should be 409
    And the error should indicate "UserAlreadyExists"
