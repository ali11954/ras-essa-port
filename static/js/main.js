// Global Configuration
const CONFIG = {
    apiBaseUrl: '/api',
    dateFormat: 'YYYY-MM-DD',
    itemsPerPage: 10
};

// Document Ready
$(document).ready(function() {
    initializeTooltips();
    initializePopovers();
    setupAjaxLoading();
    setupFormValidation();
    initializeCharts();
    initializeDatePickers();
    handleAutoCloseAlerts();
});

// Initialize Bootstrap Tooltips
function initializeTooltips() {
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function(tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
}

// Initialize Popovers
function initializePopovers() {
    var popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    popoverTriggerList.map(function(popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });
}

// Setup AJAX Loading Overlay
function setupAjaxLoading() {
    $(document).ajaxStart(function() {
        $('.spinner-wrapper').fadeIn('fast');
    });

    $(document).ajaxStop(function() {
        $('.spinner-wrapper').fadeOut('fast');
    });

    $(document).ajaxError(function(event, jqxhr, settings, thrownError) {
        $('.spinner-wrapper').fadeOut('fast');
        showNotification('حدث خطأ في الاتصال بالخادم', 'error');
    });
}

// Form Validation
function setupFormValidation() {
    $('form').on('submit', function(e) {
        let isValid = true;
        const form = $(this);

        // Check required fields
        form.find('[required]').each(function() {
            if (!$(this).val()) {
                isValid = false;
                markFieldAsInvalid($(this), 'هذا الحقل مطلوب');
            } else {
                markFieldAsValid($(this));
            }
        });

        // Email validation
        form.find('input[type="email"]').each(function() {
            if ($(this).val() && !isValidEmail($(this).val())) {
                isValid = false;
                markFieldAsInvalid($(this), 'البريد الإلكتروني غير صحيح');
            }
        });

        // Phone validation
        form.find('input[name="phone"]').each(function() {
            if ($(this).val() && !isValidPhone($(this).val())) {
                isValid = false;
                markFieldAsInvalid($(this), 'رقم الهاتف غير صحيح');
            }
        });

        if (!isValid) {
            e.preventDefault();
            showNotification('يرجى تصحيح الأخطاء في النموذج', 'error');
        }
    });
}

// Mark field as invalid
function markFieldAsInvalid(field, message) {
    field.addClass('is-invalid');
    if (!field.next('.invalid-feedback').length) {
        field.after('<div class="invalid-feedback">' + message + '</div>');
    }
}

// Mark field as valid
function markFieldAsValid(field) {
    field.removeClass('is-invalid');
    field.next('.invalid-feedback').remove();
}

// Email validation
function isValidEmail(email) {
    const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return re.test(String(email).toLowerCase());
}

// Phone validation
function isValidPhone(phone) {
    const re = /^[0-9]{10,14}$/;
    return re.test(String(phone).replace(/[^0-9]/g, ''));
}

// Initialize Charts
function initializeCharts() {
    // Dashboard charts are initialized in their respective templates
}

// Initialize Date Pickers
function initializeDatePickers() {
    $('input[type="date"]').each(function() {
        if (!$(this).val()) {
            $(this).val(new Date().toISOString().split('T')[0]);
        }
    });
}

// Handle Auto-close Alerts
function handleAutoCloseAlerts() {
    setTimeout(function() {
        $('.alert').fadeOut('slow');
    }, 5000);
}

// Show Notification
function showNotification(message, type = 'info') {
    const toast = `
        <div class="position-fixed top-0 end-0 p-3" style="z-index: 99999">
            <div class="toast align-items-center text-white bg-${type === 'error' ? 'danger' : type} border-0" role="alert">
                <div class="d-flex">
                    <div class="toast-body">
                        <i class="fas fa-${type === 'success' ? 'check-circle' : type === 'error' ? 'exclamation-circle' : 'info-circle'} me-2"></i>
                        ${message}
                    </div>
                    <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
                </div>
            </div>
        </div>
    `;

    $('body').append(toast);
    $('.toast').toast('show');

    setTimeout(function() {
        $('.position-fixed').remove();
    }, 5000);
}

// Confirmation Dialog
function confirmAction(message, callback) {
    Swal.fire({
        title: 'تأكيد العملية',
        text: message,
        icon: 'question',
        showCancelButton: true,
        confirmButtonColor: '#3085d6',
        cancelButtonColor: '#d33',
        confirmButtonText: 'نعم',
        cancelButtonText: 'إلغاء'
    }).then((result) => {
        if (result.isConfirmed && callback) {
            callback();
        }
    });
}

// Export to Excel
function exportToExcel(tableId, filename) {
    const table = document.getElementById(tableId);
    const wb = XLSX.utils.table_to_book(table, { sheet: "Sheet1" });
    XLSX.writeFile(wb, filename + '_' + new Date().toISOString().split('T')[0] + '.xlsx');

    showNotification('تم تصدير البيانات بنجاح', 'success');
}

// Print Function
function printElement(elementId) {
    const printContent = document.getElementById(elementId).innerHTML;
    const originalContent = document.body.innerHTML;

    document.body.innerHTML = `
        <div class="container mt-4">
            <h2 class="text-center mb-4">ميناء رأس عيسى</h2>
            ${printContent}
        </div>
    `;

    window.print();
    document.body.innerHTML = originalContent;
    location.reload();
}

// Format Number
function formatNumber(num) {
    return num.toString().replace(/(\d)(?=(\d{3})+(?!\d))/g, '$1,');
}

// Get URL Parameters
function getUrlParams() {
    const params = {};
    window.location.search.substring(1).split('&').forEach(function(param) {
        const [key, value] = param.split('=');
        if (key) params[key] = decodeURIComponent(value || '');
    });
    return params;
}

// Search Function
function searchTable(inputId, tableId) {
    const input = document.getElementById(inputId);
    const filter = input.value.toUpperCase();
    const table = document.getElementById(tableId);
    const tr = table.getElementsByTagName('tr');

    for (let i = 1; i < tr.length; i++) {
        const td = tr[i].getElementsByTagName('td');
        let found = false;

        for (let j = 0; j < td.length; j++) {
            if (td[j] && td[j].innerHTML.toUpperCase().indexOf(filter) > -1) {
                found = true;
                break;
            }
        }

        tr[i].style.display = found ? '' : 'none';
    }
}

// Debounce Function
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Initialize search with debounce
const debouncedSearch = debounce(function(inputId, tableId) {
    searchTable(inputId, tableId);
}, 300);

// Make functions globally available
window.showNotification = showNotification;
window.confirmAction = confirmAction;
window.exportToExcel = exportToExcel;
window.printElement = printElement;
window.formatNumber = formatNumber;
window.debouncedSearch = debouncedSearch;