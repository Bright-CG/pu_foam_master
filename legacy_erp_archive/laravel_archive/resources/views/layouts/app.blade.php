<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="X-UA-Compatible" content="ie=edge">
    <title>@yield('title', 'Archive') — Solar Foam Legacy ERP</title>

    <!-- Google Fonts -->
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Outfit:wght@500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">

    <!-- Bootstrap 5.3.3 CSS -->
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet" integrity="sha384-QWTKZyjpPEjISv5WaRU9OFeRpok6YctnYmDr5pNlyT2bRjXh0JMhjY6hW+ALEwIH" crossorigin="anonymous">

    <!-- Font Awesome 6 -->
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css" integrity="sha512-DTOQO9RWCH3ppGqcWaEA1BIZOC6xxalwEsw9c2QQeAIftl+Vegovlnee1c9QX4TctnWMn13TZye+giMm8e2LwA==" crossorigin="anonymous" referrerpolicy="no-referrer" />

    <style>
        :root {
            --sidebar-bg: #1a1f36;
            --sidebar-hover: #252b48;
            --sidebar-text: #94a3b8;
            --sidebar-text-active: #ffffff;
            --accent-emerald: #10b981;
            --accent-emerald-dark: #059669;
            --accent-emerald-light: #d1fae5;
            --content-bg: #f8fafc;
            --card-border: #e2e8f0;
            --text-dark: #1e293b;
            --text-muted: #64748b;
        }

        body {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background-color: var(--content-bg);
            color: var(--text-dark);
            min-height: 100vh;
        }

        h1, h2, h3, h4, h5, h6, .brand-title {
            font-family: 'Outfit', sans-serif;
            letter-spacing: -0.015em;
        }

        .font-mono, .amount, .code-pill {
            font-family: 'JetBrains Mono', Consolas, Monaco, monospace;
            font-variant-numeric: tabular-nums;
        }

        /* Sidebar Styling */
        #sidebar {
            width: 270px;
            min-height: 100vh;
            background-color: var(--sidebar-bg);
            color: var(--sidebar-text);
            position: fixed;
            top: 0;
            left: 0;
            z-index: 1040;
            transition: all 0.25s ease-in-out;
            box-shadow: 2px 0 10px rgba(0, 0, 0, 0.15);
        }

        .sidebar-brand {
            padding: 1.5rem 1.25rem 1.25rem;
            border-bottom: 1px solid rgba(255, 255, 255, 0.08);
            background: rgba(0, 0, 0, 0.15);
        }

        .brand-icon {
            width: 38px;
            height: 38px;
            background: linear-gradient(135deg, #10b981, #059669);
            color: white;
            border-radius: 8px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            font-size: 1.2rem;
            box-shadow: 0 4px 6px -1px rgba(16, 185, 129, 0.3);
        }

        .sidebar-menu {
            padding: 1.25rem 0.75rem;
        }

        .nav-category {
            font-size: 0.7rem;
            text-transform: uppercase;
            font-weight: 700;
            letter-spacing: 0.08em;
            color: #64748b;
            padding: 0.75rem 0.75rem 0.35rem;
        }

        .sidebar-nav-link {
            display: flex;
            align-items: center;
            padding: 0.7rem 0.85rem;
            color: var(--sidebar-text);
            border-radius: 8px;
            margin-bottom: 0.25rem;
            font-weight: 500;
            font-size: 0.92rem;
            text-decoration: none;
            transition: all 0.15s ease-in-out;
        }

        .sidebar-nav-link i {
            width: 22px;
            font-size: 1.05rem;
            margin-right: 0.75rem;
            text-align: center;
            transition: transform 0.15s;
        }

        .sidebar-nav-link:hover {
            color: var(--sidebar-text-active);
            background-color: var(--sidebar-hover);
        }

        .sidebar-nav-link:hover i {
            transform: translateX(2px);
        }

        .sidebar-nav-link.active {
            color: #ffffff;
            background-color: var(--accent-emerald);
            font-weight: 600;
            box-shadow: 0 4px 10px rgba(16, 185, 129, 0.35);
        }

        .sidebar-nav-link.active i {
            color: #ffffff;
        }

        /* Top Navbar */
        #topbar {
            height: 65px;
            background-color: #ffffff;
            border-bottom: 1px solid var(--card-border);
            padding: 0 1.5rem;
            display: flex;
            align-items: center;
            justify-content: space-between;
            position: sticky;
            top: 0;
            z-index: 1020;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
        }

        /* Main Content Wrapper */
        #main-wrapper {
            margin-left: 270px;
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            transition: all 0.25s ease-in-out;
        }

        .content-area {
            flex: 1;
            padding: 1.75rem 2rem 2.5rem;
        }

        /* Footer */
        .app-footer {
            background-color: #ffffff;
            border-top: 1px solid var(--card-border);
            padding: 1rem 2rem;
            color: var(--text-muted);
            font-size: 0.84rem;
        }

        /* Buttons & Badges */
        .btn-emerald {
            background-color: var(--accent-emerald);
            color: #ffffff;
            border: 1px solid var(--accent-emerald);
            font-weight: 500;
            transition: all 0.15s;
        }
        .btn-emerald:hover, .btn-emerald:focus {
            background-color: var(--accent-emerald-dark);
            border-color: var(--accent-emerald-dark);
            color: #ffffff;
            box-shadow: 0 4px 10px rgba(16, 185, 129, 0.25);
        }

        .btn-outline-emerald {
            color: var(--accent-emerald);
            border-color: var(--accent-emerald);
        }
        .btn-outline-emerald:hover {
            background-color: var(--accent-emerald);
            border-color: var(--accent-emerald);
            color: #ffffff;
        }

        .badge-archive {
            background-color: #f1f5f9;
            color: #475569;
            border: 1px solid #cbd5e1;
            font-weight: 600;
            font-size: 0.75rem;
            padding: 0.35em 0.65em;
        }

        .badge-positive {
            background-color: #fef2f2;
            color: #dc2626;
            border: 1px solid #fecaca;
        }

        .badge-zero {
            background-color: #ecfdf5;
            color: #059669;
            border: 1px solid #a7f3d0;
        }

        /* Cards */
        .card {
            border: 1px solid var(--card-border);
            border-radius: 10px;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
            background-color: #ffffff;
        }

        .card-header {
            background-color: #ffffff;
            border-bottom: 1px solid var(--card-border);
            font-weight: 600;
            font-family: 'Outfit', sans-serif;
            padding: 1rem 1.25rem;
        }

        /* Tables */
        .table {
            margin-bottom: 0;
            vertical-align: middle;
            font-size: 0.9rem;
        }

        .table thead th {
            background-color: #f8fafc;
            color: #475569;
            font-weight: 600;
            font-size: 0.78rem;
            text-transform: uppercase;
            letter-spacing: 0.04em;
            border-bottom: 2px solid #e2e8f0;
            padding: 0.85rem 0.75rem;
            white-space: nowrap;
        }

        .table tbody td {
            padding: 0.8rem 0.75rem;
            color: #334155;
            border-bottom: 1px solid #f1f5f9;
        }

        .table-hover tbody tr:hover {
            background-color: #f8fafc;
        }

        .row-has-balance {
            background-color: #fffbeb !important;
        }
        .table-hover tbody tr.row-has-balance:hover {
            background-color: #fef3c7 !important;
        }

        /* Form Controls */
        .form-control, .form-select {
            border-color: #cbd5e1;
            font-size: 0.9rem;
            border-radius: 6px;
        }
        .form-control:focus, .form-select:focus {
            border-color: var(--accent-emerald);
            box-shadow: 0 0 0 3px rgba(16, 185, 129, 0.15);
        }

        /* Pagination custom styling */
        .pagination {
            margin-bottom: 0;
            gap: 2px;
        }
        .page-link {
            color: #334155;
            border-radius: 6px !important;
            border: 1px solid #e2e8f0;
            margin: 0 2px;
            font-size: 0.875rem;
            padding: 0.4rem 0.75rem;
        }
        .page-link:hover {
            background-color: #f1f5f9;
            color: var(--accent-emerald);
            border-color: #cbd5e1;
        }
        .page-item.active .page-link {
            background-color: var(--accent-emerald);
            border-color: var(--accent-emerald);
            color: #ffffff;
            box-shadow: 0 2px 4px rgba(16, 185, 129, 0.3);
        }

        /* Mobile overlay & sidebar collapse */
        .sidebar-overlay {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0, 0, 0, 0.5);
            z-index: 1030;
        }

        @media (max-width: 991.98px) {
            #sidebar {
                margin-left: -270px;
            }
            #sidebar.show {
                margin-left: 0;
            }
            #main-wrapper {
                margin-left: 0;
            }
            .sidebar-overlay.show {
                display: block;
            }
            .content-area {
                padding: 1.25rem 1rem 2rem;
            }
        }

        /* Print styles */
        @media print {
            body {
                background: #ffffff !important;
                color: #000000 !important;
                font-size: 11pt;
            }
            #sidebar, #topbar, .app-footer, .no-print, .btn, .pagination, form.search-form, .sidebar-overlay {
                display: none !important;
            }
            #main-wrapper {
                margin-left: 0 !important;
                padding: 0 !important;
                min-height: auto !important;
            }
            .content-area {
                padding: 0 !important;
            }
            .card {
                border: 1px solid #ccc !important;
                box-shadow: none !important;
                break-inside: avoid;
            }
            .card-header {
                background: #f1f5f9 !important;
                color: #000000 !important;
            }
            .table {
                width: 100% !important;
                border-collapse: collapse !important;
            }
            .table th, .table td {
                color: #000000 !important;
                border: 1px solid #cbd5e1 !important;
                padding: 6px 8px !important;
            }
            .print-header {
                display: block !important;
                margin-bottom: 20px;
                border-bottom: 2px solid #1a1f36;
                padding-bottom: 10px;
            }
            .badge {
                border: 1px solid #333 !important;
                color: #000 !important;
                background: transparent !important;
            }
            a {
                text-decoration: none !important;
                color: #000 !important;
            }
        }

        .print-header {
            display: none;
        }
    </style>
</head>
<body>

    <!-- Sidebar Overlay for Mobile -->
    <div class="sidebar-overlay" id="sidebarOverlay" onclick="toggleSidebar()"></div>

    <!-- Sidebar -->
    <aside id="sidebar">
        <div class="sidebar-brand">
            <div class="d-flex align-items-center">
                <div class="brand-icon me-2">
                    <i class="fa-solid fa-cube"></i>
                </div>
                <div class="lh-1 overflow-hidden">
                    <div class="brand-title text-white fw-bold text-truncate" style="font-size: 0.95rem;">
                        Solar Foam &amp; Chemical
                    </div>
                    <div class="text-xs text-uppercase mt-1" style="font-size: 0.65rem; color: #10b981; letter-spacing: 0.05em; font-weight: 600;">
                        Legacy ERP Archive
                    </div>
                </div>
            </div>
            <div class="mt-2 text-muted small" style="font-size: 0.72rem; color: #94a3b8;">
                Pre-ERPNext Historical Records
            </div>
        </div>

        <div class="sidebar-menu">
            <div class="nav-category">Main Navigation</div>

            <a href="{{ route('dashboard') }}" class="sidebar-nav-link {{ request()->routeIs('dashboard') ? 'active' : '' }}">
                <i class="fa-solid fa-house"></i>
                <span>Home</span>
            </a>

            <div class="nav-category mt-3">Primary archives</div>

            <a href="{{ route('customers.index') }}" class="sidebar-nav-link {{ request()->routeIs('customers.*') ? 'active' : '' }}">
                <i class="fa-solid fa-users"></i>
                <span>Customer statements</span>
            </a>

            <a href="{{ route('suppliers.index') }}" class="sidebar-nav-link {{ request()->routeIs('suppliers.*') ? 'active' : '' }}">
                <i class="fa-solid fa-truck"></i>
                <span>Supplier statements</span>
            </a>

            <a href="{{ route('gl.index') }}" class="sidebar-nav-link {{ request()->routeIs('gl.index') || request()->routeIs('gl.show') ? 'active' : '' }}">
                <i class="fa-solid fa-book-journal-whills"></i>
                <span>General ledger</span>
            </a>
        </div>

        <!-- Sidebar Bottom Info -->
        <div class="position-absolute bottom-0 start-0 end-0 p-3" style="border-top: 1px solid rgba(255,255,255,0.08); background: rgba(0,0,0,0.2);">
            <div class="d-flex align-items-center justify-content-between text-muted" style="font-size: 0.75rem;">
                <div>
                    <i class="fa-solid fa-database text-success me-1"></i>
                    <span>Read-Only SQLite</span>
                </div>
                <span class="badge bg-secondary-subtle text-light border border-secondary" style="font-size: 0.65rem;">Archive</span>
            </div>
        </div>
    </aside>

    <!-- Main Wrapper -->
    <div id="main-wrapper">
        <!-- Top Navbar -->
        <header id="topbar" class="no-print">
            <div class="d-flex align-items-center">
                <button class="btn btn-sm btn-light border d-lg-none me-2" onclick="toggleSidebar()" type="button" aria-label="Toggle Navigation">
                    <i class="fa-solid fa-bars"></i>
                </button>
                <div class="d-none d-sm-block">
                    <span class="text-muted small">Solar Foam and Chemical Industries Nigeria Ltd</span>
                    <span class="mx-2 text-muted">•</span>
                    <span class="badge bg-emerald text-white rounded-pill" style="background-color: var(--accent-emerald); font-size: 0.7rem;">Legacy ERP</span>
                </div>
            </div>

            <div class="d-flex align-items-center gap-2">
                <!-- Print Page Button -->
                <button type="button" onclick="window.print()" class="btn btn-sm btn-outline-secondary d-flex align-items-center gap-2" title="Print this page">
                    <i class="fa-solid fa-print"></i>
                    <span class="d-none d-md-inline">Print</span>
                </button>

                <!-- User & Logout -->
                <div class="dropdown">
                    <button class="btn btn-sm btn-light border dropdown-toggle d-flex align-items-center gap-2" type="button" data-bs-toggle="dropdown" aria-expanded="false">
                        <i class="fa-solid fa-user-circle text-secondary"></i>
                        <span class="d-none d-md-inline">{{ session('archive_user', 'Administrator') }}</span>
                    </button>
                    <ul class="dropdown-menu dropdown-menu-end shadow-sm">
                        <li>
                            <h6 class="dropdown-header">System Access</h6>
                        </li>
                        <li>
                            <span class="dropdown-item-text small text-muted">
                                <i class="fa-solid fa-shield-halved me-1 text-success"></i> Read-Only Session
                            </span>
                        </li>
                        <li><hr class="dropdown-divider"></li>
                        <li>
                            <form action="{{ route('logout') }}" method="POST" class="m-0">
                                @csrf
                                <button type="submit" class="dropdown-item text-danger d-flex align-items-center gap-2">
                                    <i class="fa-solid fa-right-from-bracket"></i>
                                    <span>Logout</span>
                                </button>
                            </form>
                        </li>
                    </ul>
                </div>
            </div>
        </header>

        <!-- Print-only Header -->
        <div class="print-header px-4 pt-3">
            <div class="d-flex justify-content-between align-items-center">
                <div>
                    <h3 class="fw-bold mb-0">Solar Foam and Chemical Industries Nigeria Ltd</h3>
                    <div class="text-muted small">Legacy ERP Archive — Historical Statement</div>
                </div>
                <div class="text-end small text-muted">
                    <div>Printed on: {{ now()->format('d-M-Y H:i') }}</div>
                    <div>Source: happifoam.db</div>
                </div>
            </div>
        </div>

        <!-- Main Content Area -->
        <main class="content-area">
            @yield('content')
        </main>

        <!-- Footer -->
        <footer class="app-footer no-print">
            <div class="d-flex flex-column flex-md-row justify-content-between align-items-center gap-2">
                <div>
                    <span class="fw-semibold text-dark">Solar Foam &amp; Chemical Industries Nigeria Ltd</span>
                    <span class="text-muted ms-1">— Legacy Archive (Data from 18-Oct-2021 onwards)</span>
                </div>
                <div class="text-muted small">
                    <i class="fa-solid fa-lock text-emerald me-1" style="color: var(--accent-emerald);"></i> Read-Only Enterprise Historical Archive
                </div>
            </div>
        </footer>
    </div>

    <!-- Bootstrap 5.3.3 JS Bundle -->
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js" integrity="sha384-YvpcrYf0tY3lHB60NNkmXc5s9fDVZLESaAA55NDzOxhy9GkcIdslK1eN7N6jIeHz" crossorigin="anonymous"></script>

    <script>
        function toggleSidebar() {
            const sidebar = document.getElementById('sidebar');
            const overlay = document.getElementById('sidebarOverlay');
            sidebar.classList.toggle('show');
            overlay.classList.toggle('show');
        }
    </script>

    @yield('scripts')
</body>
</html>
