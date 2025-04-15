document.addEventListener("DOMContentLoaded", passwordValidator);


function passwordValidator(){

    
        const passwordInput = document.getElementById("password");
        const confirmPasswordInput = document.getElementById("confirm-password");
        const submitButton = document.querySelector("button[type='submit']");
        const confirmPasswordGroup = confirmPasswordInput.closest('.sign-up-form-group');
        
        // Create validation message elements
        const validationContainer = document.createElement("div");
        validationContainer.classList.add("password-validation");

        // Validation rules
        const rules = [
            { id: "length", text: "At least 6 characters long", check: (pw) => pw.length >= 6 },
            { id: "uppercase", text: "At least one uppercase letter", check: (pw) => /[A-Z]/.test(pw) },
            { id: "match", text: "Passwords must match", check: (pw) => pw === confirmPasswordInput.value }
        ];

        // Generate validation list dynamically
        rules.forEach(rule => {
            const item = document.createElement("p");
            item.id = rule.id;
            item.innerHTML = `❌ ${rule.text}`;
            item.style.display = "none"; // Initially hidden
            validationContainer.appendChild(item);
        });

        
        confirmPasswordGroup.parentNode.insertBefore(validationContainer, confirmPasswordGroup.nextSibling)

        function validatePassword() {
            const password = passwordInput.value;
            let isValid = true;

            rules.forEach(rule => {
                const item = document.getElementById(rule.id);
                if (password) {
                    item.style.display = "block"; // Show only after typing starts
                }
                if (rule.check(password)) {
                    item.innerHTML = `✅ ${rule.text}`;
                    item.style.color = "green";
                } else {
                    item.innerHTML = `❌ ${rule.text}`;
                    item.style.color = "red";
                    isValid = false;
                }
            });

            // Re-check password match separately
            const matchRule = document.getElementById("match");
            if (confirmPasswordInput.value) {
                matchRule.style.display = "block"; // Show only after typing
            }
            if (password === confirmPasswordInput.value) {
                matchRule.innerHTML = `✅ Passwords must match`;
                matchRule.style.color = "green";
            } else {
                matchRule.innerHTML = `❌ Passwords must match`;
                matchRule.style.color = "red";
                isValid = false;
            }

            submitButton.disabled = !isValid; // Enable only if all checks pass
        }

        // Event listeners for real-time validation
        passwordInput.addEventListener("input", validatePassword);
        confirmPasswordInput.addEventListener("input", validatePassword);

        // Show validation on focus (but not before typing)
        passwordInput.addEventListener("focus", () => {
            rules.forEach(rule => {
                document.getElementById(rule.id).style.display = "block";
            });
        });

       
    

}