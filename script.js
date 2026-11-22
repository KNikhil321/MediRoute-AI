// MediRoute AI - Client-side helpers

document.addEventListener('DOMContentLoaded', function () {
    // Sidebar toggle for mobile
    const toggleBtn = document.getElementById('sidebarToggle');
    const sidebar = document.getElementById('sidebar');
    if (toggleBtn && sidebar) {
        toggleBtn.addEventListener('click', function () {
            sidebar.classList.toggle('show');
        });
        // Close sidebar when clicking outside on mobile
        document.addEventListener('click', function (e) {
            if (window.innerWidth < 992 &&
                !sidebar.contains(e.target) &&
                !toggleBtn.contains(e.target) &&
                sidebar.classList.contains('show')) {
                sidebar.classList.remove('show');
            }
        });
    }

    // Auto-dismiss alerts after 6 seconds
    document.querySelectorAll('.alert-dismissible').forEach(function (alert) {
        setTimeout(function () {
            const bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
            if (bsAlert) bsAlert.close();
        }, 6000);
    });

    // Confirm reset demo data
    const resetBtn = document.getElementById('resetDemoBtn');
    if (resetBtn) {
        resetBtn.addEventListener('click', function (e) {
            if (!confirm('This will delete ALL current data and reload sample doctors + reports. Continue?')) {
                e.preventDefault();
            }
        });
    }

    // Character counter for report description
    const desc = document.getElementById('description');
    const counter = document.getElementById('descCounter');
    if (desc && counter) {
        desc.addEventListener('input', function () {
            const len = this.value.length;
            counter.textContent = len + ' / 4000';
            if (len < 20) {
                counter.classList.add('text-danger');
                counter.classList.remove('text-muted');
            } else {
                counter.classList.remove('text-danger');
                counter.classList.add('text-muted');
            }
        });
    }
});