// User Dashboard Script
document.addEventListener('DOMContentLoaded', function() {
    // Product selection handler
    const productSelect = document.getElementById('product-select');
    const productDetails = document.getElementById('product-details');
    const productCost = document.getElementById('product-cost');
    const productDuration = document.getElementById('product-duration');
    const generateBtn = document.getElementById('generate-key');
    const generatedKeyDiv = document.getElementById('generated-key');
    const keyDisplay = document.querySelector('.key-display');

    if (productSelect) {
        productSelect.addEventListener('change', function() {
            const selectedOption = this.options[this.selectedIndex];
            if (this.value) {
                const cost = selectedOption.dataset.cost;
                const days = selectedOption.dataset.days;
                productCost.textContent = cost;
                productDuration.textContent = days;
                productDetails.style.display = 'block';
                generateBtn.disabled = false;
            } else {
                productDetails.style.display = 'none';
                generateBtn.disabled = true;
            }
        });
    }

    // Generate key handler
    if (generateBtn) {
        generateBtn.addEventListener('click', function() {
            const productId = productSelect.value;
            
            fetch('/generate_key', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ product_id: productId })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    keyDisplay.textContent = data.key;
                    generatedKeyDiv.style.display = 'block';
                    
                    // Refresh the page after 2 seconds to show updated credits and keys
                    setTimeout(() => {
                        location.reload();
                    }, 2000);
                } else {
                    alert('Error: ' + data.error);
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('An error occurred while generating the key');
            });
        });
    }

    // HWID Reset handlers
    const hwidResetAll = document.getElementById('hwid-reset-all');
    
    if (hwidResetAll) {
        hwidResetAll.addEventListener('click', function() {
            if (!confirm('Are you sure you want to reset HWID for all your licenses?')) return;
            
            fetch('/hwid_reset_all', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                }
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    alert('All HWIDs reset successfully');
                    location.reload();
                } else {
                    alert('Error: ' + data.error);
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('An error occurred');
            });
        });
    }

    // Individual HWID Reset
    document.querySelectorAll('.btn-hwid-reset').forEach(btn => {
        btn.addEventListener('click', function() {
            if (!confirm('Reset HWID for this license?')) return;
            
            const licenseId = this.dataset.licenseId;
            
            fetch('/hwid_reset', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ license_id: licenseId })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    alert('HWID reset successful');
                    location.reload();
                } else {
                    alert('Error: ' + data.error);
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('An error occurred');
            });
        });
    });

    // Admin Dashboard Scripts
    const tabs = document.querySelectorAll('.tab-btn');
    const tabContents = document.querySelectorAll('.tab-content');

    if (tabs.length > 0) {
        tabs.forEach(tab => {
            tab.addEventListener('click', function() {
                const tabName = this.dataset.tab;
                
                // Remove active class from all tabs and contents
                tabs.forEach(t => t.classList.remove('active'));
                tabContents.forEach(c => c.classList.remove('active'));
                
                // Add active class to current tab and content
                this.classList.add('active');
                document.getElementById(tabName + '-tab').classList.add('active');
            });
        });
    }

    // Add Product
    const addProductBtn = document.getElementById('add-product-btn');
    const addProductForm = document.getElementById('add-product-form');
    const cancelProductBtn = document.getElementById('cancel-product');
    const saveProductBtn = document.getElementById('save-product');

    if (addProductBtn) {
        addProductBtn.addEventListener('click', function() {
            addProductForm.style.display = 'block';
        });
    }

    if (cancelProductBtn) {
        cancelProductBtn.addEventListener('click', function() {
            addProductForm.style.display = 'none';
            // Clear form
            document.getElementById('new-product-name').value = '';
            document.getElementById('new-product-cost').value = '';
            document.getElementById('new-product-price').value = '';
        });
    }

    if (saveProductBtn) {
        saveProductBtn.addEventListener('click', function() {
            const name = document.getElementById('new-product-name').value;
            const credit_cost = document.getElementById('new-product-cost').value;
            const days = document.getElementById('new-product-days').value;
            const price = document.getElementById('new-product-price').value;
            const key_type = document.getElementById('new-product-keytype').value;

            if (!name || !credit_cost || !price) {
                alert('Please fill all fields');
                return;
            }

            fetch('/admin/add_product', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    name: name,
                    credit_cost: credit_cost,
                    days: days,
                    price: price,
                    key_type: key_type
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    alert('Product added successfully');
                    location.reload();
                } else {
                    alert('Error: ' + (data.error || 'Failed to add product'));
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('An error occurred');
            });
        });
    }

    // Edit Product
    const editProductModal = document.getElementById('edit-product-modal');
    const editProductId = document.getElementById('edit-product-id');
    const editProductName = document.getElementById('edit-product-name');
    const editProductCost = document.getElementById('edit-product-cost');
    const editProductDays = document.getElementById('edit-product-days');
    const editProductPrice = document.getElementById('edit-product-price');
    const editProductKeyType = document.getElementById('edit-product-keytype');
    const updateProductBtn = document.getElementById('update-product');
    const closeModalBtn = document.getElementById('close-modal');

    document.querySelectorAll('.btn-edit-product').forEach(btn => {
        btn.addEventListener('click', function() {
            const productId = this.dataset.productId;
            const row = this.closest('tr');
            const cells = row.querySelectorAll('td');
            
            editProductId.value = productId;
            editProductName.value = cells[0].textContent;
            editProductCost.value = cells[1].textContent;
            
            // Handle days dropdown
            const days = cells[2].textContent.replace(' days', '');
            Array.from(editProductDays.options).forEach(option => {
                if (option.value === days) {
                    option.selected = true;
                }
            });
            
            editProductPrice.value = cells[3].textContent.replace('₹', '');
            
            // Handle key type dropdown
            const keyType = cells[4].textContent;
            Array.from(editProductKeyType.options).forEach(option => {
                if (option.value === keyType) {
                    option.selected = true;
                }
            });
            
            editProductModal.style.display = 'flex';
        });
    });

    if (updateProductBtn) {
        updateProductBtn.addEventListener('click', function() {
            const productId = editProductId.value;
            const name = editProductName.value;
            const credit_cost = editProductCost.value;
            const days = editProductDays.value;
            const price = editProductPrice.value;
            const key_type = editProductKeyType.value;

            fetch('/admin/edit_product', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    product_id: productId,
                    name: name,
                    credit_cost: credit_cost,
                    days: days,
                    price: price,
                    key_type: key_type
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    alert('Product updated successfully');
                    location.reload();
                } else {
                    alert('Failed to update product');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('An error occurred');
            });
        });
    }

    if (closeModalBtn) {
        closeModalBtn.addEventListener('click', function() {
            editProductModal.style.display = 'none';
        });
    }

    // Delete Product
    document.querySelectorAll('.btn-delete-product').forEach(btn => {
        btn.addEventListener('click', function() {
            if (!confirm('Are you sure you want to delete this product?')) return;
            
            const productId = this.dataset.productId;
            
            fetch('/admin/delete_product', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ product_id: productId })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    alert('Product deleted successfully');
                    location.reload();
                } else {
                    alert('Failed to delete product');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('An error occurred');
            });
        });
    });

    // Approve Payment
    document.querySelectorAll('.btn-approve-payment').forEach(btn => {
        btn.addEventListener('click', function() {
            if (!confirm('Approve this payment?')) return;
            
            const paymentId = this.dataset.paymentId;
            
            fetch('/admin/approve_payment', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ payment_id: paymentId })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    alert('Payment approved successfully');
                    location.reload();
                } else {
                    alert('Failed to approve payment');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('An error occurred');
            });
        });
    });

    // Add Credits
    const addCreditsModal = document.getElementById('add-credits-modal');
    const addCreditsUsername = document.getElementById('add-credits-username');
    const addCreditsAmount = document.getElementById('add-credits-amount');
    const confirmAddCredits = document.getElementById('confirm-add-credits');
    const closeCreditsModal = document.getElementById('close-credits-modal');

    document.querySelectorAll('.btn-add-credits').forEach(btn => {
        btn.addEventListener('click', function() {
            const username = this.dataset.username;
            addCreditsUsername.value = username;
            addCreditsModal.style.display = 'flex';
        });
    });

    if (confirmAddCredits) {
        confirmAddCredits.addEventListener('click', function() {
            const username = addCreditsUsername.value;
            const credits = addCreditsAmount.value;

            if (!credits || credits < 1) {
                alert('Please enter a valid amount');
                return;
            }

            fetch('/admin/add_credits', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    username: username,
                    credits: credits
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    alert('Credits added successfully');
                    location.reload();
                } else {
                    alert('Failed to add credits');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('An error occurred');
            });
        });
    }

    if (closeCreditsModal) {
        closeCreditsModal.addEventListener('click', function() {
            addCreditsModal.style.display = 'none';
            addCreditsAmount.value = '';
        });
    }

    // Delete User
    document.querySelectorAll('.btn-delete-user').forEach(btn => {
        btn.addEventListener('click', function() {
            if (!confirm('Are you sure you want to delete this user? This action cannot be undone.')) return;
            
            const username = this.dataset.username;
            
            fetch('/admin/delete_user', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ username: username })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    alert('User deleted successfully');
                    location.reload();
                } else {
                    alert('Failed to delete user');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('An error occurred');
            });
        });
    });

    // Delete Key (Admin)
    document.querySelectorAll('.btn-delete-key').forEach(btn => {
        btn.addEventListener('click', function() {
            if (!confirm('Are you sure you want to delete this key?')) return;
            
            const licenseId = this.dataset.licenseId;
            
            fetch('/admin/delete_key', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ license_id: licenseId })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    alert('Key deleted successfully');
                    location.reload();
                } else {
                    alert('Failed to delete key');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('An error occurred');
            });
        });
    });

    // Close modals when clicking outside
    window.addEventListener('click', function(event) {
        if (event.target.classList.contains('modal')) {
            event.target.style.display = 'none';
        }
    });
});
