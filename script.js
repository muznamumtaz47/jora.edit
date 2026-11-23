
/* =========================================
   MOBILE NAVIGATION
========================================= */

const menuToggle = document.getElementById("menuToggle");
const navLeft = document.getElementById("navLeft");

if (menuToggle && navLeft) {
    menuToggle.addEventListener("click", function () {
        navLeft.classList.toggle("active");
        menuToggle.classList.toggle("active");

        menuToggle.setAttribute(
            "aria-expanded",
            navLeft.classList.contains("active")
        );
    });

    document.querySelectorAll(".nav-left a").forEach(link => {
        link.addEventListener("click", function () {
            navLeft.classList.remove("active");
            menuToggle.classList.remove("active");
            menuToggle.setAttribute("aria-expanded", "false");
        });
    });

    document.addEventListener("keydown", function (event) {
        if (event.key === "Escape") {
            navLeft.classList.remove("active");
            menuToggle.classList.remove("active");
            menuToggle.setAttribute("aria-expanded", "false");
        }
    });
}


/* MOBILE COLLECTIONS DROPDOWN */

const collectionsToggle = document.getElementById("collectionsToggle");
const collectionsDropdown = document.querySelector(".dropdown");

if (collectionsToggle && collectionsDropdown) {
    collectionsToggle.addEventListener("click", function (event) {
        event.preventDefault();
        event.stopPropagation();

        const isOpen = collectionsDropdown.classList.toggle("open");
        collectionsToggle.setAttribute("aria-expanded", isOpen);
    });

    document.addEventListener("click", function (event) {
        if (!collectionsDropdown.contains(event.target)) {
            collectionsDropdown.classList.remove("open");
            collectionsToggle.setAttribute("aria-expanded", "false");
        }
    });
}

/* =========================================
   PRODUCT IMAGE VIEW SELECTOR
========================================= */

const mainImage = document.getElementById("mainProductImage");
const thumbnails = document.querySelectorAll(".thumbnail");

if (mainImage) {
    thumbnails.forEach(button => {
        button.addEventListener("click", () => {
            const view = button.dataset.view;

            mainImage.className = "main-product-image view-" + view;
            mainImage.textContent = view.toUpperCase() + " VIEW";

            thumbnails.forEach(item => item.classList.remove("active"));
            button.classList.add("active");
        });
    });
}


/* =========================================
   PRODUCT SIZE SELECTOR
========================================= */

const sizeButtons = document.querySelectorAll(".size-options button");
const selectedSize = document.getElementById("selectedSize");

if (selectedSize) {
    sizeButtons.forEach(button => {
        button.addEventListener("click", () => {
            sizeButtons.forEach(item => item.classList.remove("selected"));
            button.classList.add("selected");

            selectedSize.textContent = "Selected size: " + button.textContent;
        });
    });
}

/* ANDAAZ SLEEVE SELECTOR */

const sleeveButtons = document.querySelectorAll(".sleeve-options button");
const selectedSleeves = document.getElementById("selectedSleeves");

if (selectedSleeves) {
    sleeveButtons.forEach(button => {
        button.addEventListener("click", () => {
            sleeveButtons.forEach(item => item.classList.remove("selected"));
            button.classList.add("selected");

            selectedSleeves.textContent =
                "Selected sleeve preference: " + button.dataset.sleeves;
        });
    });
}


/* =========================================
   CART FUNCTIONS
========================================= */

function getJoraCart() {
    const cart = JSON.parse(localStorage.getItem("joraCart")) || [];

    return cart.map(item => ({
        ...item,
        quantity: Number(item.quantity) || 1
    }));
}

function saveJoraCart(cart) {
    localStorage.setItem("joraCart", JSON.stringify(cart));
    updateBagCount();
}

function escapeCartText(value) {
    return String(value).replace(/[&<>"']/g, character => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#039;"
    })[character]);
}


/* =========================================
   PRICE AND PAYMENT CALCULATIONS
========================================= */

const SHIPPING_CHARGES = 300;

function getItemPrice(price) {
    const numericPrice = Number(
        String(price).replace(/[^\d.]/g, "")
    );

    return Number.isFinite(numericPrice) && numericPrice > 0
        ? numericPrice
        : 0;
}

function formatPKR(amount) {
    return "PKR " + Number(amount).toLocaleString("en-PK");
}

function calculateCheckout(cart, preference = "50% Advance") {
    let subtotal = 0;
    let hasUnknownPrice = false;

    cart.forEach(item => {
        const price = getItemPrice(item.price);
        const quantity = Number(item.quantity) || 1;

        if (price <= 0) {
            hasUnknownPrice = true;
        } else {
            subtotal += price * quantity;
        }
    });

    const shipping = SHIPPING_CHARGES;
    const total = subtotal + shipping;

    let advance;
    let remaining;
    let deliveryAmount;

    if (preference === "Full Payment") {
        advance = total;
        remaining = 0;
        deliveryAmount = 0;
    } else {
        advance = Math.round(subtotal / 2);
        remaining = subtotal - advance;
        deliveryAmount = remaining + shipping;
    }

    return {
        subtotal,
        shipping,
        advance,
        remaining,
        deliveryAmount,
        total,
        hasUnknownPrice
    };
}


/* =========================================
   ADD TO BAG FUNCTIONALITY
========================================= */

const addToCartButton = document.getElementById("addToCartButton");

if (addToCartButton) {
    addToCartButton.addEventListener("click", function () {

        const productNameElement = document.querySelector(".product-info h1");
        const selectedSizeElement = document.getElementById("selectedSize");
        const selectedSleevesElement = document.getElementById("selectedSleeves");

        if (!productNameElement || !selectedSizeElement) return;

        const productName = productNameElement.textContent.trim();
        const selectedSizeText = selectedSizeElement.textContent.trim();

        if (!selectedSizeText.startsWith("Selected size:")) {
            alert("Please select your size first!");
            return;
        }

        const selectedSizeValue = selectedSizeText
            .replace("Selected size:", "")
            .trim();

        let sleevePreference = "";

        if (productName.toUpperCase() === "ANDAAZ") {

            const sleeveText = selectedSleevesElement
                ? selectedSleevesElement.textContent.trim()
                : "";

            if (!sleeveText.startsWith("Selected sleeve preference:")) {
                alert("Please select WITH SLEEVES or WITHOUT SLEEVES.");
                return;
            }

            sleevePreference = sleeveText
                .replace("Selected sleeve preference:", "")
                .trim();
        }

        const priceElement = document.querySelector(".product-price");

        if (!priceElement) {
            alert("Product price is not available.");
            return;
        }

        const price = priceElement.textContent.trim();

        const productImage = document.getElementById("mainProductImage");

        const image = productImage
            ? productImage.getAttribute("src")
            : "";

        const cart = getJoraCart();

        const existingItem = cart.find(item =>
            item.name === productName &&
            item.size === selectedSizeValue &&
            (item.sleeves || "") === sleevePreference
        );

        if (existingItem) {
            existingItem.quantity += 1;
        } else {
            cart.push({
                name: productName,
                size: selectedSizeValue,
                sleeves: sleevePreference,
                price,
                image,
                quantity: 1
            });
        }

        saveJoraCart(cart);

        alert("Your outfit has been added to your bag!");
    });
}



/* =========================================
   UPDATE BAG COUNT
========================================= */

function updateBagCount() {
    const cart = getJoraCart();
    const bagCount = document.getElementById("bagCount");

    if (bagCount) {
        const totalQuantity = cart.reduce(
            (total, item) => total + item.quantity,
            0
        );

        bagCount.textContent = totalQuantity;
    }
}

updateBagCount();


/* =========================================
   DISPLAY CART ITEMS
========================================= */

const cartItemsContainer = document.getElementById("cartItems");

if (cartItemsContainer) {

    function displayCart() {
        const cart = getJoraCart();
        const cartTotal = document.getElementById("cartTotal");

        if (cart.length === 0) {
            cartItemsContainer.innerHTML = `
                <div class="empty-cart">
                    <h2>Your bag is waiting.</h2>
                    <p>
                        Discover something beautiful from our collection.
                    </p>
                    <a href="collections.html" class="back-link">
                        EXPLORE THE COLLECTION →
                    </a>
                </div>
            `;

            if (cartTotal) cartTotal.textContent = "Rs. 0";
            return;
        }

        cartItemsContainer.innerHTML = "";

        let subtotal = 0;
        let hasUnknownPrice = false;

        cart.forEach((item, index) => {
            const numericPrice = getItemPrice(item.price);

            if (numericPrice > 0) {
                subtotal += numericPrice * item.quantity;
            } else {
                hasUnknownPrice = true;
            }

            const product = document.createElement("div");
            product.className = "cart-item";

            product.innerHTML = `
                <div class="cart-item-image">
                    ${
                        item.image
                        ? `<img src="${escapeCartText(item.image)}" alt="Product image">`
                        : ""
                    }
                </div>

                <div class="cart-item-details">
                    <h3>${escapeCartText(item.name)}</h3>

                    <p class="cart-category">
                        THE JORA.EDIT COLLECTION
                    </p>

                    <p class="cart-size">
                        Size: ${escapeCartText(item.size)}
                    </p>
${item.sleeves ? `
    <p class="cart-size">
        Sleeves: ${escapeCartText(item.sleeves)}
    </p>
` : ""}
                    <p class="cart-price">
                        ${escapeCartText(item.price)}
                    </p>

                    <div class="quantity-control">
                        <button type="button" class="quantity-btn"
                            data-action="minus" data-index="${index}">−</button>

                        <span>${item.quantity}</span>

                        <button type="button" class="quantity-btn"
                            data-action="plus" data-index="${index}">+</button>
                    </div>

                    <button type="button" class="remove-item"
                        data-action="remove" data-index="${index}">
                        REMOVE
                    </button>
                </div>
            `;

            cartItemsContainer.appendChild(product);
        });

        if (cartTotal) {
            cartTotal.textContent = hasUnknownPrice
                ? "To be announced"
                : formatPKR(subtotal);
        }
    }

    cartItemsContainer.addEventListener("click", function (event) {
        const button = event.target.closest("button[data-action]");
        if (!button) return;

        const index = Number(button.dataset.index);
        const action = button.dataset.action;
        const cart = getJoraCart();
        const item = cart[index];

        if (!item) return;

        if (action === "plus") item.quantity += 1;

        if (action === "minus") {
            item.quantity -= 1;

            if (item.quantity <= 0) {
                cart.splice(index, 1);
            }
        }

        if (action === "remove") {
            cart.splice(index, 1);
        }

        saveJoraCart(cart);
        displayCart();
    });

    displayCart();
}


/* =========================================
   GO TO CHECKOUT
========================================= */

const checkoutButton = document.getElementById("checkoutButton");

if (checkoutButton) {
    checkoutButton.addEventListener("click", function () {
        const cart = getJoraCart();

        if (cart.length === 0) {
            alert("Your shopping bag is empty!");
            return;
        }

        window.location.href = "checkout.html";
    });
}


/* =========================================
   CHECKOUT PAYMENT SYSTEM
========================================= */

const checkoutItems = document.getElementById("checkoutItems");

if (checkoutItems) {

    const cart = getJoraCart();

    const subtotalElement = document.getElementById("checkoutSubtotal");
    const shippingElement = document.getElementById("checkoutShipping");
    const totalElement = document.getElementById("checkoutTotal");
    const advanceElement = document.getElementById("checkoutAdvance");
    const remainingElement = document.getElementById("checkoutRemaining");
    const advanceLabel = document.getElementById("checkoutAdvanceLabel");

    const paymentPreferenceInputs = document.querySelectorAll(
        'input[name="paymentPreference"]'
    );

    const paymentMethodInputs = document.querySelectorAll(
        'input[name="paymentMethod"]'
    );

    const paymentInstructions = document.getElementById("paymentInstructions");
    const paymentAccountDetails = document.getElementById("paymentAccountDetails");

    function getSelectedPreference() {
        const selected = document.querySelector(
            'input[name="paymentPreference"]:checked'
        );

        return selected ? selected.value : "50% Advance";
    }

    function getSelectedPaymentMethod() {
        const selected = document.querySelector(
            'input[name="paymentMethod"]:checked'
        );

        return selected ? selected.value : "";
    }

    function updatePaymentSummary() {
        const preference = getSelectedPreference();
        const amounts = calculateCheckout(cart, preference);

        if (subtotalElement) {
            subtotalElement.textContent = amounts.hasUnknownPrice
                ? "Price unavailable"
                : formatPKR(amounts.subtotal);
        }

        if (shippingElement) {
            shippingElement.textContent = formatPKR(amounts.shipping);
        }

        if (totalElement) {
            totalElement.textContent = amounts.hasUnknownPrice
                ? "Price unavailable"
                : formatPKR(amounts.total);
        }

        if (advanceElement) {
            advanceElement.textContent = amounts.hasUnknownPrice
                ? "Price unavailable"
                : formatPKR(amounts.advance);
        }

        if (remainingElement) {
            remainingElement.textContent = amounts.hasUnknownPrice
                ? "Price unavailable"
                : formatPKR(amounts.deliveryAmount);
        }

        if (advanceLabel) {
            advanceLabel.textContent = preference === "Full Payment"
                ? "Full Payment"
                : "Advance Payment (50%)";
        }

        return amounts;
    }

    function updatePaymentDetails() {
        const method = getSelectedPaymentMethod();

        if (!paymentInstructions || !paymentAccountDetails) return;

        if (method === "Bank Transfer") {
            paymentInstructions.textContent =
                "Transfer your payment to the following MCB Bank account:";

            paymentAccountDetails.textContent =
                "Bank: MCB Bank | Account Title: ABDULLAH MUMTAZ | " +
                "Account Number: 1699773021011622 | " +
                "IBAN: PK95MUCB1699773021011622";

        } else if (method === "NayaPay Personal Transfer") {
            paymentInstructions.textContent =
                "Transfer your payment to the following NayaPay account:";

            paymentAccountDetails.textContent =
                "Account Title: Muzna Mumtaz | Account Number: 03184333282";

        } else {
            paymentInstructions.textContent =
                "Please select a payment method.";

            paymentAccountDetails.textContent = "";
        }
    }

    if (cart.length === 0) {
        checkoutItems.innerHTML = "<p>Your bag is empty.</p>";

        if (subtotalElement) subtotalElement.textContent = "PKR 0";
        if (shippingElement) shippingElement.textContent = formatPKR(SHIPPING_CHARGES);
        if (totalElement) totalElement.textContent = "PKR 0";
        if (advanceElement) advanceElement.textContent = "PKR 0";
        if (remainingElement) remainingElement.textContent = "PKR 0";

    } else {
        cart.forEach(item => {
            const div = document.createElement("div");
            div.className = "checkout-product";

            const name = document.createElement("strong");
            name.textContent = item.name;

            const size = document.createElement("p");
            size.textContent = "Size: " + item.size;
            if (item.sleeves) {
    const sleeves = document.createElement("p");
    sleeves.textContent = "Sleeves: " + item.sleeves;
    div.appendChild(sleeves);
}

            const quantity = document.createElement("p");
            quantity.textContent = "Quantity: " + (Number(item.quantity) || 1);

            const price = document.createElement("p");
            price.textContent = item.price;

            div.append(name, size, quantity, price);
            checkoutItems.appendChild(div);
        });

        updatePaymentSummary();
    }

    paymentPreferenceInputs.forEach(input => {
        input.addEventListener("change", updatePaymentSummary);
    });

    paymentMethodInputs.forEach(input => {
        input.addEventListener("change", updatePaymentDetails);
    });

    updatePaymentDetails();
}


/* =========================================
   SUBMIT CUSTOMER ORDER
========================================= */

const checkoutForm = document.getElementById("checkoutForm");

if (checkoutForm) {

    checkoutForm.addEventListener("submit", async function (event) {
        event.preventDefault();

        const cart = getJoraCart();

        if (cart.length === 0) {
            alert("Your shopping bag is empty!");
            return;
        }

        const paymentPreference = document.querySelector(
            'input[name="paymentPreference"]:checked'
        );

        const paymentMethod = document.querySelector(
            'input[name="paymentMethod"]:checked'
        );

        const transactionInput = document.getElementById("transactionId");
        const screenshotInput = document.getElementById("paymentScreenshot");

        if (!paymentPreference) {
            alert("Please select 50% Advance or Full Payment.");
            return;
        }

        if (!paymentMethod) {
            alert("Please select MCB Bank or NayaPay.");
            return;
        }

        if (!transactionInput || !transactionInput.value.trim()) {
            alert("Please enter your transaction ID.");
            return;
        }

        if (!screenshotInput || !screenshotInput.files.length) {
            alert("Please upload your payment screenshot.");
            return;
        }

        const screenshot = screenshotInput.files[0];

        const allowedTypes = [
            "image/jpeg",
            "image/png",
            "image/webp"
        ];

        if (!allowedTypes.includes(screenshot.type)) {
            alert("Please upload a JPG, PNG or WEBP image.");
            return;
        }

        if (screenshot.size > 5 * 1024 * 1024) {
            alert("Payment screenshot must be smaller than 5 MB.");
            return;
        }

        const amounts = calculateCheckout(cart, paymentPreference.value);

        if (amounts.hasUnknownPrice) {
            alert("A product price is missing. Please contact JORA.EDIT.");
            return;
        }

        const formData = new FormData();

        formData.append(
            "name",
            document.getElementById("customerName").value.trim()
        );

        formData.append(
            "phone",
            document.getElementById("customerPhone").value.trim()
        );

        formData.append(
            "email",
            document.getElementById("customerEmail").value.trim()
        );

        formData.append(
            "city",
            document.getElementById("customerCity").value.trim()
        );

        formData.append(
            "address",
            document.getElementById("customerAddress").value.trim()
        );

        formData.append("payment_method", paymentMethod.value);
        formData.append("payment_preference", paymentPreference.value);
        formData.append("transaction_id", transactionInput.value.trim());

        formData.append(
            "products",
            JSON.stringify(cart.map(item => ({
                name: item.name,
                size: item.size,
                 sleeves: item.sleeves || "",
    quantity: Number(item.quantity) || 1
            })))
        );

        formData.append("payment_screenshot", screenshot);

        const submitButton = checkoutForm.querySelector(
            'button[type="submit"]'
        );

        if (submitButton) {
            submitButton.disabled = true;
            submitButton.textContent = "SUBMITTING ORDER...";
        }

        try {
            const response = await fetch("/api/place-order", {
                method: "POST",
                body: formData
            });

            const result = await response.json();

            if (!response.ok || !result.success) {
                throw new Error(
                    result.message || "Order could not be placed."
                );
            }

            localStorage.removeItem("joraCart");

            window.location.href =
                "order-success.html?order=" + result.order_id;

        } catch (error) {
            alert(
                error.message || "Something went wrong. Please try again."
            );

            if (submitButton) {
                submitButton.disabled = false;
                submitButton.textContent = "PLACE MY ORDER ↗";
            }
        }
    });
}


/* =========================================
   PRODUCT IMAGE CHANGE
========================================= */

function changeImage(thumbnail) {
    const image = document.getElementById("mainProductImage");

    if (!image) return;

    image.src = thumbnail.src;

    document.querySelectorAll(".thumbnail").forEach(img => {
        img.classList.remove("active");
    });

    thumbnail.classList.add("active");
}


/* =========================================
   NEWSLETTER POPUP
========================================= */

const newsletterPopup = document.getElementById("newsletterPopup");

if (newsletterPopup) {

    const closeNewsletter = document.getElementById("closeNewsletter");
    const newsletterLater = document.getElementById("newsletterLater");
    const newsletterForm = document.getElementById("newsletterForm");

    function hideNewsletter() {
        newsletterPopup.classList.remove("show");
        localStorage.setItem("joraNewsletterDismissed", "yes");
    }

    if (!localStorage.getItem("joraNewsletterDismissed")) {
        setTimeout(() => {
            newsletterPopup.classList.add("show");
        }, 3000);
    }

    if (closeNewsletter) {
        closeNewsletter.addEventListener("click", hideNewsletter);
    }

    if (newsletterLater) {
        newsletterLater.addEventListener("click", hideNewsletter);
    }

    newsletterPopup.addEventListener("click", function (event) {
        if (event.target === newsletterPopup) {
            hideNewsletter();
        }
    });

    if (newsletterForm) {
        newsletterForm.addEventListener("submit", async function (event) {
            event.preventDefault();

            const email = document.getElementById("newsletterEmail").value.trim();
            const message = document.getElementById("newsletterMessage");
            const button = this.querySelector("button");

            button.disabled = true;
            button.textContent = "SUBSCRIBING...";

            try {
                const response = await fetch("/api/subscribe", {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json"
                    },
                    body: JSON.stringify({ email })
                });

                const result = await response.json();

                if (!response.ok || !result.success) {
                    throw new Error(
                        result.message || "Something went wrong."
                    );
                }

                message.textContent = result.message;
                this.reset();

                localStorage.setItem("joraNewsletterDismissed", "yes");

                setTimeout(() => {
                    hideNewsletter();
                }, 2000);

            } catch (error) {
                message.textContent =
                    error.message || "Please try again.";
            }

            button.disabled = false;
            button.textContent = "SUBSCRIBE";
        });
    }
}

function openSizeChart(design) {
    const image = document.getElementById("sizeChartImage");
    const popup = document.getElementById("sizeChartPopup");

    if (!image || !popup) return;

    if (design === "gulrukh") {
        image.src = "images/gulrukh-size-chart.jpeg";
    } else if (design === "raqs") {
        image.src = "images/raqs-size-chart.jpeg";
    } else if (design === "andaaz") {
        image.src = "images/andaaz-size-chart.jpeg";
    }

    popup.classList.add("active");
}

function closeSizeChart() {
    const popup = document.getElementById("sizeChartPopup");

    if (popup) {
        popup.classList.remove("active");
    }
}
