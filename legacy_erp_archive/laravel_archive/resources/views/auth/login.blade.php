<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="X-UA-Compatible" content="ie=edge">
    <title>Login — Solar Foam Legacy ERP Archive</title>

    <!-- Google Fonts -->
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Outfit:wght@500;600;700;800&display=swap" rel="stylesheet">

    <!-- Bootstrap 5.3.3 CSS -->
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet" integrity="sha384-QWTKZyjpPEjISv5WaRU9OFeRpok6YctnYmDr5pNlyT2bRjXh0JMhjY6hW+ALEwIH" crossorigin="anonymous">

    <!-- Font Awesome 6 -->
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css" integrity="sha512-DTOQO9RWCH3ppGqcWaEA1BIZOC6xxalwEsw9c2QQeAIftl+Vegovlnee1c9QX4TctnWMn13TZye+giMm8e2LwA==" crossorigin="anonymous" referrerpolicy="no-referrer" />

    <style>
        :root {
            --accent-emerald: #10b981;
            --accent-emerald-dark: #059669;
        }

        body {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: linear-gradient(135deg, #1a1f36 0%, #0f172a 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 1.5rem;
            color: #e2e8f0;
        }

        h1, h2, h3, h4, h5, h6, .brand-title {
            font-family: 'Outfit', sans-serif;
        }

        .login-card {
            background-color: #ffffff;
            border-radius: 14px;
            box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.4), 0 8px 10px -6px rgba(0, 0, 0, 0.3);
            width: 100%;
            max-width: 440px;
            overflow: hidden;
            border: 1px solid rgba(255, 255, 255, 0.1);
            color: #1e293b;
        }

        .login-header {
            background: #1e293b;
            padding: 2.25rem 2rem 2rem;
            text-align: center;
            border-bottom: 1px solid #334155;
            position: relative;
        }

        .brand-icon-lg {
            width: 54px;
            height: 54px;
            background: linear-gradient(135deg, #10b981, #059669);
            color: white;
            border-radius: 12px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            font-size: 1.6rem;
            margin-bottom: 1rem;
            box-shadow: 0 10px 15px -3px rgba(16, 185, 129, 0.4);
        }

        .login-body {
            padding: 2.25rem 2rem 2rem;
        }

        .btn-emerald {
            background-color: var(--accent-emerald);
            color: #ffffff;
            border: none;
            font-weight: 600;
            padding: 0.75rem 1.25rem;
            border-radius: 8px;
            font-size: 0.95rem;
            transition: all 0.2s ease-in-out;
            box-shadow: 0 4px 6px -1px rgba(16, 185, 129, 0.3);
        }

        .btn-emerald:hover, .btn-emerald:focus {
            background-color: var(--accent-emerald-dark);
            color: #ffffff;
            box-shadow: 0 8px 15px -3px rgba(16, 185, 129, 0.4);
            transform: translateY(-1px);
        }

        .form-control {
            border-color: #cbd5e1;
            padding: 0.7rem 0.85rem;
            border-radius: 8px;
            font-size: 0.95rem;
        }

        .form-control:focus {
            border-color: var(--accent-emerald);
            box-shadow: 0 0 0 3px rgba(16, 185, 129, 0.18);
        }

        .input-group-text {
            background-color: #f8fafc;
            border-color: #cbd5e1;
            color: #64748b;
            border-radius: 8px 0 0 8px;
        }

        .input-group .form-control {
            border-radius: 0 8px 8px 0;
        }

        .login-footer-note {
            background-color: #f8fafc;
            border-top: 1px solid #e2e8f0;
            padding: 1rem 1.5rem;
            text-align: center;
            font-size: 0.8rem;
            color: #64748b;
        }
    </style>
</head>
<body>

    <div class="login-card">
        <!-- Header -->
        <div class="login-header">
            <div class="brand-icon-lg">
                <i class="fa-solid fa-cube"></i>
            </div>
            <h4 class="text-white fw-bold mb-1">Solar Foam &amp; Chemical</h4>
            <div class="text-secondary small">Industries Nigeria Ltd</div>
            <div class="mt-2">
                <span class="badge rounded-pill text-uppercase px-3 py-1" style="background-color: rgba(16, 185, 129, 0.15); color: #34d399; font-size: 0.72rem; letter-spacing: 0.05em; border: 1px solid rgba(16, 185, 129, 0.3);">
                    Legacy ERP Archive
                </span>
            </div>
        </div>

        <!-- Body -->
        <div class="login-body">
            @if ($errors->any())
                <div class="alert alert-danger d-flex align-items-center mb-4 py-2 px-3 small border-0" role="alert" style="background-color: #fef2f2; color: #991b1b; border-left: 4px solid #ef4444 !important;">
                    <i class="fa-solid fa-circle-exclamation me-2 fs-6"></i>
                    <div>
                        @foreach ($errors->all() as $error)
                            <div>{{ $error }}</div>
                        @endforeach
                    </div>
                </div>
            @endif

            <form action="{{ route('login.submit') }}" method="POST">
                @csrf

                <div class="mb-3">
                    <label for="username" class="form-label text-dark fw-semibold small">Username</label>
                    <div class="input-group">
                        <span class="input-group-text"><i class="fa-solid fa-user"></i></span>
                        <input type="text" class="form-control @error('username') is-invalid @enderror" id="username" name="username" value="{{ old('username', 'admin') }}" required autofocus autocomplete="username" placeholder="Enter username">
                    </div>
                </div>

                <div class="mb-4">
                    <label for="password" class="form-label text-dark fw-semibold small">Password</label>
                    <div class="input-group">
                        <span class="input-group-text"><i class="fa-solid fa-lock"></i></span>
                        <input type="password" class="form-control @error('password') is-invalid @enderror" id="password" name="password" required autocomplete="current-password" placeholder="Enter password">
                    </div>
                </div>

                <button type="submit" class="btn btn-emerald w-100 d-flex align-items-center justify-content-center gap-2">
                    <i class="fa-solid fa-vault"></i>
                    <span>Access Archive</span>
                </button>
            </form>
        </div>

        <!-- Footer Notice -->
        <div class="login-footer-note">
            <i class="fa-solid fa-circle-info text-emerald me-1" style="color: var(--accent-emerald);"></i>
            This is a read-only archive of historical ERP data.
        </div>
    </div>

    <!-- Bootstrap 5.3.3 JS Bundle -->
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js" integrity="sha384-YvpcrYf0tY3lHB60NNkmXc5s9fDVZLESaAA55NDzOxhy9GkcIdslK1eN7N6jIeHz" crossorigin="anonymous"></script>
</body>
</html>
