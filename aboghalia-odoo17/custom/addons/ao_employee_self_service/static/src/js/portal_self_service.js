/** @odoo-module **/

document.addEventListener('DOMContentLoaded', function () {
    console.log('Enterprise Electronic Portal JS Initialized with F5 Reload Persistence.');

    // Helper for Odoo JSON-RPC 2.0 requests
    async function jsonRpc(url, params = {}) {
        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest'
            },
            body: JSON.stringify({
                jsonrpc: '2.0',
                method: 'call',
                params: params,
                id: Math.floor(Math.random() * 1000000)
            })
        });

        if (!response.ok) {
            throw new Error(`HTTP Error ${response.status}: ${response.statusText}`);
        }

        const data = await response.json();
        if (data.error) {
            throw new Error(data.error.data?.message || data.error.message || 'JSON-RPC Error');
        }

        return data.result;
    }

    // Header Backend Button Permission Handler
    const btnBackend = document.getElementById('ess_btn_backend');
    if (btnBackend) {
        btnBackend.addEventListener('click', function (e) {
            e.preventDefault();
            const hasAccess = btnBackend.getAttribute('data-has-access') === 'true';
            if (hasAccess) {
                window.location.href = '/web';
            } else {
                alert('تنبيه: ليس لديك صلاحيات الوصول للواجهة الخلفية للنظام. سيتم تحديث الصفحة الحالية.');
                window.location.reload();
            }
        });
    }

    // Check-In / Check-Out Handling with GPS Location
    const checkInOutBtn = document.getElementById('ess_btn_checkinout');
    if (checkInOutBtn) {
        checkInOutBtn.addEventListener('click', async function (e) {
            e.preventDefault();
            e.stopPropagation();
            checkInOutBtn.style.pointerEvents = 'none';
            const origText = checkInOutBtn.innerHTML;
            checkInOutBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> جاري تحديد الموقع...';

            let locationData = { latitude: null, longitude: null, location_name: null };

            if (navigator.geolocation) {
                try {
                    const pos = await new Promise((resolve, reject) => {
                        navigator.geolocation.getCurrentPosition(resolve, reject, {
                            enableHighAccuracy: true,
                            timeout: 8000,
                            maximumAge: 60000
                        });
                    });
                    locationData.latitude = pos.coords.latitude;
                    locationData.longitude = pos.coords.longitude;
                    locationData.location_name = `${pos.coords.latitude.toFixed(4)}, ${pos.coords.longitude.toFixed(4)}`;
                } catch (geoErr) {
                    console.warn('Geolocation unavailable or denied:', geoErr);
                }
            }

            checkInOutBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> جاري المعالجة...';

            try {
                const res = await jsonRpc('/portal/self-service/check_in_out', locationData);

                if (res.success) {
                    alert(res.message);
                    window.location.reload();
                } else {
                    alert('خطأ: ' + (res.message || 'فشلت العملية'));
                    checkInOutBtn.style.pointerEvents = 'auto';
                    checkInOutBtn.innerHTML = origText;
                }
            } catch (err) {
                console.error('Check-in error:', err);
                alert('حدث خطأ في الاتصال بالسيرفر: ' + err.message);
                checkInOutBtn.style.pointerEvents = 'auto';
                checkInOutBtn.innerHTML = origText;
            }
        });
    }

    // Modals Event Delegation
    document.addEventListener('click', function (e) {
        const leaveModalTrigger = e.target.closest('.ess-open-leave-modal');
        if (leaveModalTrigger) {
            e.preventDefault();
            const modalLeave = document.getElementById('ess_modal_leave');
            if (modalLeave) modalLeave.classList.add('active');
            return;
        }

        const genericModalTrigger = e.target.closest('.ess-open-generic-modal');
        if (genericModalTrigger) {
            e.preventDefault();
            const serviceName = genericModalTrigger.getAttribute('data-service-name') || 'طلب خدمة';
            const titleEl = document.getElementById('ess_generic_modal_title');
            if (titleEl) titleEl.innerText = serviceName;
            const modalGeneric = document.getElementById('ess_modal_generic');
            if (modalGeneric) modalGeneric.classList.add('active');
            return;
        }

        const taskModalTrigger = e.target.closest('.ess-open-task-modal');
        if (taskModalTrigger) {
            e.preventDefault();
            const modalTask = document.getElementById('ess_modal_task');
            if (modalTask) modalTask.classList.add('active');
            return;
        }

        const modalCloseBtn = e.target.closest('.ess-modal-close');
        if (modalCloseBtn) {
            document.querySelectorAll('.ess-modal').forEach(m => m.classList.remove('active'));
            return;
        }
    });

    // Submit Leave Request Form
    const formLeave = document.getElementById('ess_form_leave');
    if (formLeave) {
        formLeave.addEventListener('submit', async function (e) {
            e.preventDefault();
            const submitBtn = formLeave.querySelector('button[type="submit"]');
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> جاري الإرسال...';

            const payload = {
                holiday_status_id: document.getElementById('ess_leave_type').value,
                date_from: document.getElementById('ess_leave_from').value,
                date_to: document.getElementById('ess_leave_to').value,
                description: document.getElementById('ess_leave_desc').value
            };

            try {
                const res = await jsonRpc('/portal/self-service/submit_leave', payload);
                if (res.success) {
                    alert(res.message);
                    window.location.reload();
                } else {
                    alert('خطأ: ' + res.message);
                    submitBtn.disabled = false;
                    submitBtn.innerHTML = 'تقديم الطلب الان';
                }
            } catch (err) {
                alert('فشل الاتصال بالسيرفر: ' + err.message);
                submitBtn.disabled = false;
                submitBtn.innerHTML = 'تقديم الطلب الان';
            }
        });
    }

    // Submit Task Creation Form
    const formTask = document.getElementById('ess_form_task');
    if (formTask) {
        formTask.addEventListener('submit', async function (e) {
            e.preventDefault();
            const submitBtn = formTask.querySelector('button[type="submit"]');
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> جاري إضافة المهمة...';

            const payload = {
                name: document.getElementById('ess_task_name').value,
                description: document.getElementById('ess_task_desc').value,
                task_type: document.getElementById('ess_task_type').value,
                assigned_to_id: document.getElementById('ess_task_assignee') ? document.getElementById('ess_task_assignee').value : null,
                priority: document.getElementById('ess_task_priority').value,
                date_deadline: document.getElementById('ess_task_deadline').value
            };

            try {
                const res = await jsonRpc('/portal/self-service/task/create', payload);
                if (res.success) {
                    alert(res.message);
                    window.location.reload();
                } else {
                    alert('خطأ: ' + res.message);
                    submitBtn.disabled = false;
                    submitBtn.innerHTML = 'إضافة المهمة الان';
                }
            } catch (err) {
                alert('فشل الاتصال بالسيرفر: ' + err.message);
                submitBtn.disabled = false;
                submitBtn.innerHTML = 'إضافة المهمة الان';
            }
        });
    }

    // Profile Editor Form Submit
    const avatarInput = document.getElementById('ess_profile_avatar_input');
    const avatarPreview = document.getElementById('ess_profile_avatar_preview');
    let avatarBase64 = null;

    if (avatarInput && avatarPreview) {
        avatarInput.addEventListener('change', function () {
            const file = avatarInput.files[0];
            if (file) {
                const reader = new FileReader();
                reader.onload = function (e) {
                    avatarPreview.src = e.target.result;
                    avatarBase64 = e.target.result;
                };
                reader.readAsDataURL(file);
            }
        });
    }

    const formProfile = document.getElementById('ess_form_profile');
    if (formProfile) {
        formProfile.addEventListener('submit', async function (e) {
            e.preventDefault();
            const submitBtn = formProfile.querySelector('button[type="submit"]');
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> جاري الحفظ...';

            const payload = {
                mobile_phone: document.getElementById('ess_prof_mobile').value,
                work_phone: document.getElementById('ess_prof_work_phone').value,
                private_email: document.getElementById('ess_prof_email').value,
                emergency_contact: document.getElementById('ess_prof_emg_name').value,
                emergency_phone: document.getElementById('ess_prof_emg_phone').value,
                street: document.getElementById('ess_prof_street').value,
                city: document.getElementById('ess_prof_city').value,
                avatar_base64: avatarBase64
            };

            try {
                const res = await jsonRpc('/portal/self-service/profile/update', payload);
                if (res.success) {
                    alert(res.message);
                    window.location.reload();
                } else {
                    alert('خطأ: ' + res.message);
                    submitBtn.disabled = false;
                    submitBtn.innerHTML = '<i class="fa-solid fa-floppy-disk me-1"></i> حفظ التغييرات في الملف الشخصي';
                }
            } catch (err) {
                alert('فشل الاتصال بالسيرفر: ' + err.message);
                submitBtn.disabled = false;
                submitBtn.innerHTML = '<i class="fa-solid fa-floppy-disk me-1"></i> حفظ التغييرات في الملف الشخصي';
            }
        });
    }
    // --- CTS (Administrative Communications) Portal Logic ---
    window.currentCtsFilter = 'all';

    window.essSetCtsFilter = function(filter, btnEl) {
        document.querySelectorAll('.ess-cts-filters .list-group-item').forEach(el => el.classList.remove('active'));
        if (btnEl) btnEl.classList.add('active');
        window.currentCtsFilter = filter;
        window.loadCtsTransactions(filter);
    };

    window.ctsCurrentPage = 1;
    window.ctsTotalPages = 1;

    window.ctsChangePage = function(delta) {
        let newPage = window.ctsCurrentPage + delta;
        if (newPage < 1) newPage = 1;
        if (newPage > window.ctsTotalPages) newPage = window.ctsTotalPages;
        
        if (newPage !== window.ctsCurrentPage) {
            window.ctsCurrentPage = newPage;
            if (window.location.pathname === '/my/cts') {
                initColumnMenu();
                window.ctsApplyColumns();
                window.loadCtsTransactions(window.currentCtsFilter);
            }
        }
    };
    
    // Sort and Columns State
    window.ctsSortColumn = 'create_date';
    window.ctsSortDirection = 'desc';

    const defaultCols = {
        serial_number: true, request_topic: true, customer_name: true,
        request_mode: true, creator_name: true, assigned_user: true,
        priority: true, state: true, start_date: false, end_date: true, actions: true
    };
    const colLabels = {
        serial_number: 'رقم المعاملة', request_topic: 'الموضوع', customer_name: 'اسم العميل / الجهة',
        request_mode: 'الاتجاه', creator_name: 'المنشئ', assigned_user: 'الموظف المسؤول',
        priority: 'الأولوية', state: 'الحالة', start_date: 'تاريخ البداية', end_date: 'تاريخ الاستحقاق', actions: 'إجراءات'
    };

    window.ctsColumns = JSON.parse(localStorage.getItem('ess_cts_columns')) || defaultCols;

    window.ctsSort = function(col) {
        if (window.ctsSortColumn === col) {
            window.ctsSortDirection = window.ctsSortDirection === 'asc' ? 'desc' : 'asc';
        } else {
            window.ctsSortColumn = col;
            window.ctsSortDirection = 'asc';
        }
        window.ctsCurrentPage = 1;
        window.loadCtsTransactions(window.currentCtsFilter);
    };

    window.ctsToggleColumn = function(colId, checked) {
        window.ctsColumns[colId] = checked;
        localStorage.setItem('ess_cts_columns', JSON.stringify(window.ctsColumns));
        window.ctsApplyColumns();
    };

    window.ctsApplyColumns = function() {
        const table = document.querySelector('.ess-table');
        if (!table) return;
        
        Object.keys(window.ctsColumns).forEach(colId => {
            const cb = document.getElementById('col_cb_' + colId);
            if (cb) cb.checked = window.ctsColumns[colId];
            
            const isVisible = window.ctsColumns[colId];
            const displayVal = isVisible ? '' : 'none';
            
            const th = table.querySelector(`th[data-col="${colId}"]`);
            if (th) th.style.display = displayVal;
            
            const tds = table.querySelectorAll(`td[data-col="${colId}"]`);
            tds.forEach(td => td.style.display = displayVal);
        });
        
        const ths = table.querySelectorAll('th.sortable');
        ths.forEach(th => {
            const icon = th.querySelector('.sort-icon');
            if (icon) {
                icon.className = 'sort-icon fa-solid ms-1 text-muted';
                if (th.getAttribute('onclick') && th.getAttribute('onclick').includes(`'${window.ctsSortColumn}'`)) {
                    icon.classList.add(window.ctsSortDirection === 'asc' ? 'fa-sort-up' : 'fa-sort-down');
                    icon.classList.replace('text-muted', 'text-primary');
                } else {
                    icon.classList.add('fa-sort');
                }
            }
        });
    };

    function initColumnMenu() {
        const menu = document.getElementById('ess_cts_column_menu');
        if (!menu) return;
        
        let html = '';
        Object.keys(colLabels).forEach(colId => {
            if (colId === 'actions') return; // Cannot hide actions usually, or let's allow it? let's allow it but check.
            const isChecked = window.ctsColumns[colId] ? 'checked' : '';
            html += `
                <li>
                    <label class="dropdown-item d-flex align-items-center cursor-pointer">
                        <input class="form-check-input me-2 mt-0" type="checkbox" id="col_cb_${colId}" 
                               onchange="window.ctsToggleColumn('${colId}', this.checked)" ${isChecked}>
                        ${colLabels[colId]}
                    </label>
                </li>
            `;
        });
        menu.innerHTML = html;
    }
    
    // Initialize it when JS loads
    initColumnMenu();

    window.loadCtsTransactions = async function(filter = 'all') {
        const tbody = document.getElementById('cts_table_body');
        if (!tbody) return;
        
        tbody.innerHTML = '<tr><td colspan="9" class="text-center text-muted py-4"><i class="fa-solid fa-spinner fa-spin me-2"></i> جاري تحميل البيانات...</td></tr>';
        
        const searchInput = document.getElementById('ess_cts_search');
        const searchQuery = searchInput ? searchInput.value : '';
        
        const filterStatus = document.getElementById('ess_filter_status') ? document.getElementById('ess_filter_status').value : '';
        const filterPriority = document.getElementById('ess_filter_priority') ? document.getElementById('ess_filter_priority').value : '';
        const filterDateFrom = document.getElementById('ess_filter_date_from') ? document.getElementById('ess_filter_date_from').value : '';
        const filterDateTo = document.getElementById('ess_filter_date_to') ? document.getElementById('ess_filter_date_to').value : '';
        
        const limitSelect = document.getElementById('ess_cts_limit');
        const limit = limitSelect ? parseInt(limitSelect.value) : 30;
        const offset = (window.ctsCurrentPage - 1) * limit;
        
        try {
            // Load Stats
            const stats = await jsonRpc('/portal/cts/get_stats', {});
            if (stats.status === 'success') {
                // Top Cards
                const elTotal = document.getElementById('kpi_total_transactions');
                const elAvgDur = document.getElementById('kpi_avg_duration');
                const elCompleted = document.getElementById('kpi_completed');
                const elProgress = document.getElementById('kpi_in_progress');
                
                if (elTotal) elTotal.innerText = stats.total || 0;
                if (elAvgDur) elAvgDur.innerHTML = `${stats.avg_duration || 0} <span class="fs-6">أيام</span>`;
                if (elCompleted) elCompleted.innerText = stats.completed || 0;
                if (elProgress) elProgress.innerText = (stats.status_counts && stats.status_counts.in_progress) ? stats.status_counts.in_progress : 0;
                
                // Status Breakdown
                const statuses = stats.status_counts || {};
                const total = stats.total || 1; // avoid div by zero
                
                const updateBar = (id, val) => {
                    const elVal = document.getElementById(`kpi_val_${id}`);
                    const elBar = document.getElementById(`kpi_bar_${id}`);
                    if (elVal && elBar) {
                        elVal.innerText = val;
                        elBar.style.width = `${(val / total) * 100}%`;
                    }
                };
                
                updateBar('draft', statuses.draft || 0);
                updateBar('routed', statuses.routed || 0);
                updateBar('in_progress', statuses.in_progress || 0);
                updateBar('pending_external', statuses.pending_external || 0);
                updateBar('closed', (statuses.completed || 0) + (statuses.closed || 0));

                // Leaderboard - Creators
                const listCreators = document.getElementById('kpi_list_creators');
                if (listCreators) {
                    listCreators.innerHTML = '';
                    if (stats.top_creators && stats.top_creators.length > 0) {
                        stats.top_creators.forEach((c, idx) => {
                            listCreators.innerHTML += `
                                <div class="list-group-item px-0 d-flex justify-content-between align-items-center border-0 mb-1">
                                    <div>
                                        <span class="badge bg-purple rounded-circle me-2">${idx + 1}</span>
                                        <span class="fw-bold text-dark">${c.name}</span>
                                    </div>
                                    <span class="badge bg-light text-dark border px-3 rounded-pill">${c.count} معاملة</span>
                                </div>`;
                        });
                    } else {
                        listCreators.innerHTML = '<div class="text-center text-muted py-3 small">لا توجد بيانات</div>';
                    }
                }

                // Leaderboard - Responsible
                const listResponsible = document.getElementById('kpi_list_responsible');
                if (listResponsible) {
                    listResponsible.innerHTML = '';
                    if (stats.top_employees && stats.top_employees.length > 0) {
                        stats.top_employees.forEach((e, idx) => {
                            listResponsible.innerHTML += `
                                <div class="list-group-item px-0 d-flex justify-content-between align-items-center border-0 mb-1">
                                    <div>
                                        <span class="badge bg-teal rounded-circle me-2" style="background:#0d9488">${idx + 1}</span>
                                        <span class="fw-bold text-dark">${e.name}</span>
                                    </div>
                                    <span class="badge bg-light text-dark border px-3 rounded-pill">${e.count} معاملة</span>
                                </div>`;
                        });
                    } else {
                        listResponsible.innerHTML = '<div class="text-center text-muted py-3 small">لا توجد بيانات</div>';
                    }
                }

                // Update Sidebar Badges (legacy functionality)
                const bAll = document.getElementById('cts_badge_all');
                const bInc = document.getElementById('cts_badge_incoming');
                const bOut = document.getElementById('cts_badge_outgoing');
                const bInt = document.getElementById('cts_badge_internal');
                const bTask = document.getElementById('cts_badge_my_tasks');
                
                if (bAll) bAll.innerText = stats.total || 0;
                if (bInc) bInc.innerText = stats.incoming || 0;
                if (bOut) bOut.innerText = stats.outgoing || 0;
                if (bInt) bInt.innerText = (stats.mode_counts && stats.mode_counts.internal) ? stats.mode_counts.internal : 0;
                if (bTask) bTask.innerText = stats.my_tasks || 0;
            }
            
            // Load Advanced Stats
            const advStats = await jsonRpc('/portal/cts/get_advanced_stats', {});
            if (advStats.status === 'success') {
                const adv = advStats.data;
                const renderList = (id, data, iconCls, colorCls) => {
                    const el = document.getElementById(id);
                    if (!el) return;
                    el.innerHTML = '';
                    if (data && data.length > 0) {
                        data.forEach((item, idx) => {
                            el.innerHTML += `
                                <div class="list-group-item px-0 d-flex justify-content-between align-items-center border-0 mb-1">
                                    <div>
                                        <span class="badge ${colorCls} rounded-circle me-2">${idx + 1}</span>
                                        <span class="fw-bold text-dark">${item.name || 'غير محدد'}</span>
                                    </div>
                                    <span class="badge bg-light text-dark border px-3 rounded-pill">${item.count}</span>
                                </div>`;
                        });
                    } else {
                        el.innerHTML = '<div class="text-center text-muted py-3 small">لا توجد بيانات</div>';
                    }
                };
                renderList('kpi_list_companies', adv.companies, 'fa-building', 'bg-info');
                renderList('kpi_list_departments', adv.departments, 'fa-building', 'bg-info');
                renderList('kpi_list_types', adv.transaction_types, 'fa-tag', 'bg-success');
                renderList('kpi_list_priorities', adv.priorities, 'fa-star', 'bg-warning text-dark');
                renderList('kpi_list_scopes', adv.scopes, 'fa-globe', 'bg-secondary');
            }

            // Load Data
            const res = await jsonRpc('/portal/cts/get_transactions', { 
                filter_type: filter, 
                search_query: searchQuery,
                status: filterStatus,
                priority: filterPriority,
                date_from: filterDateFrom,
                date_to: filterDateTo,
                sort_by: window.ctsSortColumn + ' ' + window.ctsSortDirection,
                limit: limit,
                offset: offset
            });
            if (res.status === 'success') {
                tbody.innerHTML = '';
                if (!res.data || res.data.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="9" class="text-center text-muted py-4">لا توجد معاملات مطابقة</td></tr>';
                } else {
                    res.data.forEach(req => {
                        const tr = document.createElement('tr');
                        if (req.is_delayed) {
                            tr.classList.add('table-danger');
                        }
                        
                        let modeBadge = '';
                        if (req.request_mode === 'incoming') modeBadge = '<span class="badge bg-info">وارد</span>';
                        else if (req.request_mode === 'outgoing') modeBadge = '<span class="badge bg-warning text-dark">صادر</span>';
                        else modeBadge = '<span class="badge bg-secondary">داخلي</span>';
                        
                        let priorityBadge = '';
                        if (req.priority === 'urgent') priorityBadge = '<span class="badge bg-danger">عاجل</span>';
                        else if (req.priority === 'very_urgent') priorityBadge = '<span class="badge bg-danger">عاجل جداً</span>';
                        else if (req.priority === 'instant') priorityBadge = '<span class="badge bg-danger">فوري / سري للغاية</span>';
                        else if (req.priority === 'high') priorityBadge = '<span class="badge bg-warning text-dark">عالية</span>';
                        else priorityBadge = '<span class="badge bg-success">متوسطة / عادي</span>';
                        
                        let statusBadge = '<span class="badge border border-primary text-primary">' + (req.state || 'جديدة') + '</span>';
                        let portalLink = `/my/cts/request/${req.id}`;
                        
                        tr.innerHTML = `
                            <td data-col="serial_number"><span class="fw-bold text-primary">${req.serial_number}</span></td>
                            <td data-col="request_topic">${req.request_topic || 'بدون موضوع'}</td>
                            <td data-col="customer_name">${req.customer_name || '-'}</td>
                            <td data-col="request_mode">${modeBadge}</td>
                            <td data-col="creator_name">${req.creator_name || '-'}</td>
                            <td data-col="assigned_user">${req.assigned_user || '-'}</td>
                            <td data-col="priority">${priorityBadge}</td>
                            <td data-col="state">${statusBadge}</td>
                            <td data-col="start_date">${req.start_date || '-'}</td>
                            <td data-col="end_date">${req.end_date || '-'}</td>
                            <td data-col="actions">
                                <a href="${portalLink}" class="btn btn-sm btn-outline-primary" title="معاينة التفاصيل والمرفقات">
                                    <i class="fa-solid fa-eye"></i>
                                </a>
                            </td>
                        `;
                        tbody.appendChild(tr);
                    });
                }
                
                // Apply columns visibility
                window.ctsApplyColumns();
                
                // Update Pagination UI
                const totalCount = res.total_count || 0;
                window.ctsTotalPages = Math.ceil(totalCount / limit) || 1;
                
                const paginationEl = document.getElementById('ess_cts_pagination');
                if (paginationEl) {
                    let html = '';
                    
                    // Prev Button
                    if (window.ctsCurrentPage > 1) {
                        html += `<li class="page-item"><a class="page-link" href="javascript:void(0)" onclick="window.ctsChangePage(${window.ctsCurrentPage - 1})">السابق</a></li>`;
                    } else {
                        html += `<li class="page-item disabled"><a class="page-link" href="#" tabindex="-1" aria-disabled="true">السابق</a></li>`;
                    }
                    
                    // Pages
                    for (let i = 1; i <= window.ctsTotalPages; i++) {
                        if (i === window.ctsCurrentPage) {
                            html += `<li class="page-item active" aria-current="page"><a class="page-link" href="#">${i}</a></li>`;
                        } else {
                            html += `<li class="page-item"><a class="page-link" href="javascript:void(0)" onclick="window.ctsChangePage(${i})">${i}</a></li>`;
                        }
                    }
                    
                    // Next Button
                    if (window.ctsCurrentPage < window.ctsTotalPages) {
                        html += `<li class="page-item"><a class="page-link" href="javascript:void(0)" onclick="window.ctsChangePage(${window.ctsCurrentPage + 1})">التالي</a></li>`;
                    } else {
                        html += `<li class="page-item disabled"><a class="page-link" href="#" tabindex="-1" aria-disabled="true">التالي</a></li>`;
                    }
                    
                    paginationEl.innerHTML = html;
                }
                
            }
        } catch (err) {
            console.error('CTS Error:', err);
            tbody.innerHTML = '<tr><td colspan="7" class="text-center text-danger py-4">حدث خطأ أثناء تحميل البيانات</td></tr>';
        }
    };

    window.essOpenCtsModal = async function(id = null) {
        const modal = document.getElementById('ess_modal_cts');
        if (!modal) return;
        
        document.getElementById('ess_form_cts').reset();
        document.getElementById('ess_cts_id').value = '';
        const delBtn = document.getElementById('ess_cts_btn_delete');
        delBtn.style.display = 'none';
        
        if (id) {
            document.getElementById('ess_cts_modal_title').innerText = 'تعديل المعاملة';
            try {
                const res = await jsonRpc('/portal/cts/get_transaction_details', { req_id: id });
                if (res.status === 'success' && res.data) {
                    document.getElementById('ess_cts_id').value = res.data.id;
                    document.getElementById('ess_cts_topic').value = res.data.request_topic;
                    document.getElementById('ess_cts_mode').value = res.data.request_mode;
                    document.getElementById('ess_cts_priority').value = res.data.priority;
                    if (res.data.date_end) document.getElementById('ess_cts_date_end').value = res.data.date_end;
                    document.getElementById('ess_cts_description').value = res.data.description;
                    delBtn.style.display = 'block';
                }
            } catch (err) {
                alert('خطأ في تحميل المعاملة: ' + err.message);
                return;
            }
        } else {
            document.getElementById('ess_cts_modal_title').innerText = 'إنشاء معاملة جديدة';
        }
        modal.classList.add('active');
    };

    window.essSubmitCtsForm = async function(e) {
        e.preventDefault();
        const btn = document.querySelector('#ess_form_cts button[type="submit"]');
        btn.disabled = true;
        btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> جاري الحفظ...';
        
        const payload = {
            req_id: document.getElementById('ess_cts_id').value || null,
            request_topic: document.getElementById('ess_cts_topic').value,
            request_mode: document.getElementById('ess_cts_mode').value,
            priority: document.getElementById('ess_cts_priority').value,
            date_end: document.getElementById('ess_cts_date_end').value || null,
            description: document.getElementById('ess_cts_description').value,
        };
        
        try {
            const res = await jsonRpc('/portal/cts/save_transaction', payload);
            if (res.status === 'success') {
                document.getElementById('ess_modal_cts').classList.remove('active');
                window.loadCtsTransactions(window.currentCtsFilter);
            } else {
                alert('خطأ: ' + res.message);
            }
        } catch (err) {
            alert('حدث خطأ: ' + err.message);
        }
        
        btn.disabled = false;
        btn.innerHTML = 'حفظ وإرسال';
    };

    window.essDeleteCts = async function() {
        const id = document.getElementById('ess_cts_id').value;
        if (!id) return;
        
        if (!confirm('هل أنت متأكد من حذف هذه المعاملة نهائياً؟')) return;
        
        try {
            const res = await jsonRpc('/portal/cts/delete_transaction', { req_id: id });
            if (res.status === 'success') {
                document.getElementById('ess_modal_cts').classList.remove('active');
                window.loadCtsTransactions(window.currentCtsFilter);
            } else {
                alert('خطأ: ' + res.message);
            }
        } catch (err) {
            alert('حدث خطأ: ' + err.message);
        }
    };
    
    // Auto-load CTS if we navigate to its workspace
    const originalWorkspaceFn = window.essOpenWorkspace;
    window.essOpenWorkspace = function(tabId, title) {
        if (originalWorkspaceFn) originalWorkspaceFn(tabId, title);
        else {
            document.querySelectorAll('.ess-tab-pane').forEach(tab => tab.style.display = 'none');
            const target = document.getElementById(tabId);
            if (target) target.style.display = 'block';
            
            const titleEl = document.getElementById('ess_top_header_title');
            if (titleEl) titleEl.innerText = title;
        }
        
        if (tabId === 'tab_communications') {
            window.loadCtsTransactions(window.currentCtsFilter);
        }
    };
    
    // Initial Check: If tab is already active when JS loads, fetch data immediately
    var hash = window.location.hash.replace('#', '');
    if (hash === 'tab_communications') {
        if (!window.currentCtsFilter) window.currentCtsFilter = 'all';
        
        // Also simulate clicking the sidebar menu item to make it active visually
        const commsBtn = document.querySelector('[onclick*="essOpenWorkspace(\\\'tab_communications\\\'"]');
        if (commsBtn) {
            document.querySelectorAll('.ess-sidebar .nav-link').forEach(btn => btn.classList.remove('active', 'bg-light', 'text-primary', 'fw-bold'));
            commsBtn.classList.add('active', 'bg-light', 'text-primary', 'fw-bold');
        }
        
        window.essOpenWorkspace('tab_communications', 'نظام الاتصالات الإدارية');
    }

    // Fix for Bootstrap 5 Pills/Tabs (Advanced Stats Dashboard)
    document.querySelectorAll('.nav-pills .nav-link').forEach(btn => {
        btn.addEventListener('click', function(e) {
            e.preventDefault();
            const targetId = this.getAttribute('data-bs-target');
            if (!targetId) return;
            
            // Find the parent ul
            const ul = this.closest('ul');
            if (!ul) return;
            
            // Find the corresponding tab-content wrapper
            const tabContent = ul.nextElementSibling;
            if (!tabContent || !tabContent.classList.contains('tab-content')) return;
            
            // Deactivate all tabs in this ul
            ul.querySelectorAll('.nav-link').forEach(b => {
                b.classList.remove('active');
                b.setAttribute('aria-selected', 'false');
            });
            
            // Hide all tab panes in this content wrapper
            tabContent.querySelectorAll('.tab-pane').forEach(p => {
                p.classList.remove('show', 'active');
            });
            
            // Activate current tab
            this.classList.add('active');
            this.setAttribute('aria-selected', 'true');
            
            // Show current pane
            const targetPane = document.querySelector(targetId);
            if (targetPane) {
                targetPane.classList.add('show', 'active');
            }
        });
    });
});
