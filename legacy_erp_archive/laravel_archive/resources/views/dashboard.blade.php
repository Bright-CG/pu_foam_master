@extends('layouts.app')

@section('title', 'Legacy Archive')

@section('content')
<div class="container-fluid p-0">
    <div class="mb-4">
        <h2 class="fw-bold text-dark mb-1">Happifoam Legacy ERP Archive</h2>
        <p class="text-muted small mb-0">
            Read-only historical data from LeadingEdge webERP (from cutover {{ config('app.cutover_date', '2021-10-18') }}).
            Use the sections below for statements and general ledger.
        </p>
    </div>

    <div class="row g-3">
        <div class="col-12 col-md-4">
            <a href="{{ route('customers.index') }}" class="card h-100 shadow-sm border text-decoration-none">
                <div class="card-body p-4">
                    <div class="d-flex align-items-center gap-3 mb-2">
                        <div class="rounded-3 p-3 bg-primary-subtle text-primary">
                            <i class="fa-solid fa-users fs-4"></i>
                        </div>
                        <h5 class="fw-bold text-dark mb-0">Customer statements</h5>
                    </div>
                    <p class="text-muted small mb-0">
                        CustomerStatementBalances — debit, credit, and running balance per debtor.
                    </p>
                </div>
            </a>
        </div>
        <div class="col-12 col-md-4">
            <a href="{{ route('suppliers.index') }}" class="card h-100 shadow-sm border text-decoration-none">
                <div class="card-body p-4">
                    <div class="d-flex align-items-center gap-3 mb-2">
                        <div class="rounded-3 p-3 bg-info-subtle text-info">
                            <i class="fa-solid fa-truck fs-4"></i>
                        </div>
                        <h5 class="fw-bold text-dark mb-0">Supplier statements</h5>
                    </div>
                    <p class="text-muted small mb-0">
                        SupplierStatementBalances — creditor statements with balances.
                    </p>
                </div>
            </a>
        </div>
        <div class="col-12 col-md-4">
            <a href="{{ route('gl.index') }}" class="card h-100 shadow-sm border text-decoration-none">
                <div class="card-body p-4">
                    <div class="d-flex align-items-center gap-3 mb-2">
                        <div class="rounded-3 p-3 bg-warning-subtle text-warning">
                            <i class="fa-solid fa-book-journal-whills fs-4"></i>
                        </div>
                        <h5 class="fw-bold text-dark mb-0">General ledger</h5>
                    </div>
                    <p class="text-muted small mb-0">
                        GL account inquiry by account code and financial period.
                    </p>
                </div>
            </a>
        </div>
    </div>
</div>
@endsection
