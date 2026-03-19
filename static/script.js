// User Dashboard Script
document.addEventListener('DOMContentLoaded', function() {
    // Product selection handler
    const productSelect = document.getElementById('product-select');
    const daysSelection = document.getElementById('days-selection');
    const daysSelect = document.getElementById('days-select');
    const productDetails = document.getElementById('product-details');
    const costPerDay = document.getElementById('cost-per-day');
    const totalCredits = document.getElementById('total-credits');
    const generateBtn = document.getElementById('generate-key');
    const generatedKeyDiv = document.getElementById('generated-key');
    const keyDisplay = document.querySelector('.key-display');

    let currentProduct = null;

    if (productSelect) {
        productSelect.addEventListener('change', function() {
            const selectedOption = this.options[this.selectedIndex];
            if (this.value) {
                currentProduct = {
                    id: this.value,
                    cost: selectedOption.dataset.cost
                };
                
                costPerDay.textContent = currentProduct.cost;
                
                // Show days selection
                daysSelection.style.display = 'block';
                
                // Trigger initial calculation
                updatePriceAndCredits();
            } else {
                daysSelection.style.display = 'none';
                productDetails.style.display = 'none';
                generateBtn.disabled = true;
                currentProduct = null;
            }
        });
    }

    // Days selection handler
    if (daysSelect) {
        daysSelect.addEventListener('change', updatePriceAndCredits);
    }

    function updatePriceAndCredits() {
        if (!currentProduct) return;
        
        const days = parseInt(daysSelect.value);
        const totalCreditsValue = currentProduct.cost * days;
        
        totalCredits.textContent = totalCreditsValue;
        
        productDetails.style.display = 'block';
        generateBtn.disabled = false;
    }

    // Generate key handler
    if (generateBtn) {
        generateBtn.addEventListener('click', function() {
            if (!currentProduct) return;
            
            const days = daysSelect.value;
            
            // Disable button to prevent double click
            generateBtn.disabled = true;
            generateBtn.textContent = 'Generating...';
            
            fetch('/generate_key', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ 
                    product_id: currentProduct.id,
                    days: days
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    keyDisplay.textContent = data.key;
                    generatedKeyDiv.style.display = 'block';
                    
                    // Show success message
                    setTimeout(() => {
                        location.reload();
                    }, 3000);
                } else {
                    alert('Error: ' + data.error);
                    generateBtn.disabled = false;
                    generateBtn.textContent = 'Generate Key';
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('An error occurred while generating the key');
                generateBtn.disabled = false;
                generateBtn.textContent = 'Generate Key';
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
                
                tabs.forEach(t => t.classList.remove('active'));
                tabContents.forEach(c => c.classList.remove('active'));
                
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
            document.getElementById('new-product-name').value = '';
            document.getElementById('new-product-credits').value = '';
            document.getElementById('new-product-price').value = '';
        });
    }

    if (saveProductBtn) {
        saveProductBtn.addEventListener('click', function() {
            const name = document.getElementById('new-product-name').value;
            const credit_cost_per_day = document.getElementById('new-product-credits').value;
            const price_per_day = document.getElementById('new-product-price').value;
            const key_type = document.getElementById('new-product-keytype').value;
            const custom_pattern = document.getElementById('new-product-custom-pattern')?.value || '';

            if (!name || !credit_cost_per_day || !price_per_day) {
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
                    credit_cost_per_day: credit_cost_per_day,
                    price_per_day: price_per_day,
                    key_type: key_type,
                    custom_key_pattern: custom_pattern
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
    const editProductCredits = document.getElementById('edit-product-credits');
    const editProductPrice = document.getElementById('edit-product-price');
    const editProductKeyType = document.getElementById('edit-product-keytype');
    const editProductCustomPattern = document.getElementById('edit-product-custom-pattern');
    const updateProductBtn = document.getElementById('update-product');
    const closeModalBtn = document.getElementById('close-modal');

    document.querySelectorAll('.btn-edit-product').forEach(btn => {
        btn.addEventListener('click', function() {
            const productId = this.dataset.productId;
            const row = this.closest('tr');
            const cells = row.querySelectorAll('td');
            
            editProductId.value = productId;
            editProductName.value = cells[0].textContent;
            editProductCredits.value = cells[1].textContent;
            editProductPrice.value = cells[2].textContent.replace('₹', '');
            
            const keyType = cells[3].textContent.trim();
            Array.from(editProductKeyType.options).forEach(option => {
                if (option.value === keyType) {
                    option.selected = true;
                }
            });
            
            if (editProductCustomPattern) {
                editProductCustomPattern.value = cells[4]?.textContent.trim() || '';
            }
            
            editProductModal.style.display = 'flex';
        });
    });

    if (updateProductBtn) {
        updateProductBtn.addEventListener('click', function() {
            const productId = editProductId.value;
            const name = editProductName.value;
            const credit_cost_per_day = editProductCredits.value;
            const price_per_day = editProductPrice.value;
            const key_type = editProductKeyType.value;
            const custom_pattern = editProductCustomPattern?.value || '';

            fetch('/admin/edit_product', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    product_id: productId,
                    name: name,
                    credit_cost_per_day: credit_cost_per_day,
                    price_per_day: price_per_day,
                    key_type: key_type,
                    custom_key_pattern: custom_pattern
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

    // ============================================
    // PAYMENT ACTIONS - FIXED VERSIONS
    // ============================================

    // Approve Payment
    document.querySelectorAll('.btn-approve-payment').forEach(btn => {
        btn.addEventListener('click', function() {
            if (!confirm('Approve this payment? Credits will be added to user.')) return;
            
            const paymentId = this.dataset.paymentId;
            const originalText = this.textContent;
            
            this.disabled = true;
            this.textContent = 'Approving...';
            
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
                    alert('✅ Payment approved! Credits added to user.');
                    location.reload();
                } else {
                    alert('❌ Error: ' + (data.error || 'Failed to approve payment'));
                    this.disabled = false;
                    this.textContent = originalText;
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('❌ An error occurred');
                this.disabled = false;
                this.textContent = originalText;
            });
        });
    });

    // Reject Payment - FIXED
    document.querySelectorAll('.btn-reject-payment').forEach(btn => {
        btn.addEventListener('click', function() {
            const paymentId = this.dataset.paymentId;
            const reason = prompt('Enter rejection reason (optional):', 'Payment rejected by admin');
            
            if (reason === null) return; // User cancelled
            
            const originalText = this.textContent;
            this.disabled = true;
            this.textContent = 'Rejecting...';
            
            fetch('/admin/reject_payment', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ 
                    payment_id: paymentId,
                    reason: reason || 'Payment rejected by admin'
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    alert('✅ Payment rejected successfully');
                    location.reload();
                } else {
                    alert('❌ Error: ' + (data.error || 'Failed to reject payment'));
                    this.disabled = false;
                    this.textContent = originalText;
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('❌ An error occurred');
                this.disabled = false;
                this.textContent = originalText;
            });
        });
    });

    // Cancel Binance Order - NEW
    document.querySelectorAll('.btn-cancel-binance').forEach(btn => {
        btn.addEventListener('click', function() {
            if (!confirm('⚠️ Are you sure you want to cancel this Binance order? This will delete the order permanently.')) return;
            
            const orderId = this.dataset.orderId;
            const originalText = this.textContent;
            
            this.disabled = true;
            this.textContent = 'Cancelling...';
            
            fetch('/admin/cancel_binance_order', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ order_id: orderId })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    alert('✅ Order cancelled successfully');
                    location.reload();
                } else {
                    alert('❌ Error: ' + (data.error || 'Failed to cancel order'));
                    this.disabled = false;
                    this.textContent = originalText;
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('❌ An error occurred');
                this.disabled = false;
                this.textContent = originalText;
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

    // Toggle Product
    document.querySelectorAll('.btn-toggle-product').forEach(btn => {
        btn.addEventListener('click', function() {
            const productId = this.dataset.productId;
            const isActive = this.dataset.active === 'True' ? false : true;
            
            fetch('/admin/toggle_product', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ product_id: productId, is_active: isActive })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) location.reload();
            });
        });
    });

    // Show/hide custom pattern field
    document.getElementById('new-product-keytype')?.addEventListener('change', function() {
        const customGroup = document.getElementById('custom-pattern-group');
        if (customGroup) {
            customGroup.style.display = this.value === 'custom' ? 'block' : 'none';
        }
    });

    // Add Key Type
    document.getElementById('add-keytype-btn')?.addEventListener('click', function() {
        document.getElementById('add-keytype-form').style.display = 'block';
    });
    
    document.getElementById('cancel-keytype')?.addEventListener('click', function() {
        document.getElementById('add-keytype-form').style.display = 'none';
    });
    
    document.getElementById('save-keytype')?.addEventListener('click', function() {
        const name = document.getElementById('new-keytype-name').value;
        const pattern = document.getElementById('new-keytype-pattern').value;
        const desc = document.getElementById('new-keytype-desc').value;
        
        if (!name || !pattern) {
            alert('Name and pattern required');
            return;
        }
        
        fetch('/admin/add_key_type', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                type_name: name,
                pattern: pattern,
                description: desc
            })
        })
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                alert('Key type added');
                location.reload();
            } else {
                alert('Error: ' + data.error);
            }
        });
    });

    // Close modals when clicking outside
    window.addEventListener('click', function(event) {
        if (event.target.classList.contains('modal')) {
            event.target.style.display = 'none';
        }
    });
});
