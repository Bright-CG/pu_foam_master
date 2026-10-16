@extends('layouts.app')

@section('title', 'Trial Balance')

@section('content')
<div class="container-fluid p-0">
    <!-- Header -->
    <div class="d-flex flex-column flex-md-row justify-content-between align-items-md-center gap-3 mb-4">
        <div>
            <div class="d-flex align-items-center gap-2 mb-1">
                <h2 class="fw-bold text-dark mb-0">Trial Balance</h2>
                <span class="badge bg-secondary-subtle text-secondary border px-2 py-1">
                    {{ number_format($accounts->count()) }} Accounts
                </span>
            </div>
            <div class="text-muted small">
                General Ledger statement of debit and credit balances
            </div>
        </div>

        <div class="d-flex align-items-center gap-2 no-print">
            <a href="{{ route('gl.index') }}" class="btn btn-sm btn-outline-secondary d-flex align-items-center gap-2">
                <i class="fa-solid fa-arrow-left"></i>
                <span>Chart of Accounts</span>
            </a>
            <button onclick="window.print()" class="btn btn-emerald d-flex align-items-center gap-2 shadow-sm">
                <i class="fa-solid fa-print"></i>
                <span>Print Trial Balance</span>
            </button>
        </div>
    </div>

    <!-- Trial Balance Sheet Card -->
    <div class="card shadow-sm border">
        <div class="card-header bg-white py-3 border-bottom d-flex justify-content-between align-items-center">
            <div>
                <h5 class="fw-bold text-dark mb-0 fs-6">Solar Foam &amp; Chemical Industries Nigeria Ltd</h5>
                <div class="text-muted small">Trial Balance as at Historical Archive Date</div>
            </div>
            <div class="badge bg-light text-dark border font-mono">
                Currency: NGN
            </div>
        </div>

        <div class="card-body p-0">
            <div class="table-responsive">
                <table class="table table-striped table-hover align-middle mb-0">
                    <thead>
                        <tr>
                            <th style="width: 140px;">Account Code</th>
                            <th>Account Name</th>
                            <th style="width: 180px;">Type / Group</th>
                            <th class="text-end" style="width: 170px;">Debit (₦)</th>
                            <th class="text-end" style="width: 170px;">Credit (₦)</th>
                        </tr>
                    </thead>
                    <tbody>
                        @php
                            $totalDebit = 0;
                            $totalCredit = 0;
                        @endphp

                        @forelse($accounts as $acc)
                            @php
                                $bal = legacy_amount($acc->balance);
                                $debit = $bal >= 0 ? $bal : 0;
                                $credit = $bal < 0 ? abs($bal) : 0;
                                $totalDebit += $debit;
                                $totalCredit += $credit;
                            @endphp
                            <tr>
                                <td>
                                    <a href="{{ route('gl.show', $acc->account_code) }}" class="fw-semibold font-mono text-decoration-none text-dark">
                                        <span class="badge badge-archive font-mono">{{ $acc->account_code }}</span>
                                    </a>
                                </td>
                                <td>
                                    <a href="{{ route('gl.show', $acc->account_code) }}" class="text-decoration-none fw-semibold text-dark">
                                        {{ $acc->account_name }}
                                    </a>
                                </td>
                                <td>
                                    <span class="badge bg-light text-secondary border font-mono small">
                                        {{ $acc->account_type ?: ($acc->account_group ?: 'General') }}
                                    </span>
                                </td>
                                <td class="text-end font-mono {{ $debit > 0 ? 'text-dark' : 'text-muted' }}">
                                    {{ $debit > 0 ? number_format($debit, 2) : '—' }}
                                </td>
                                <td class="text-end font-mono {{ $credit > 0 ? 'text-dark' : 'text-muted' }}">
                                    {{ $credit > 0 ? number_format($credit, 2) : '—' }}
                                </td>
                            </tr>
                        @empty
                            <tr>
                                <td colspan="5" class="text-center py-5 text-muted">
                                    <i class="fa-solid fa-scale-unbalanced fs-1 d-block mb-3 text-secondary"></i>
                                    <h5>No Accounts Found</h5>
                                    <p class="small mb-0">No GL account balances currently available in this archive dataset.</p>
                                </td>
                            </tr>
                        @endforelse
                    </tbody>
                    <tfoot>
                        @php
                            $diff = abs($totalDebit - $totalCredit);
                            $isBalanced = $diff < 0.01;
                        @endphp
                        <tr class="table-dark text-white fw-bold">
                            <td colspan="3" class="text-uppercase font-mono ps-3">
                                Grand Totals
                            </td>
                            <td class="text-end font-mono fs-6 pe-3">
                                ₦ {{ number_format($totalDebit, 2) }}
                            </td>
                            <td class="text-end font-mono fs-6 pe-3">
                                ₦ {{ number_format($totalCredit, 2) }}
                            </td>
                        </tr>
                        @if(!$isBalanced && $accounts->count() > 0)
                            <tr class="table-warning font-mono small">
                                <td colspan="3" class="text-warning-emphasis">
                                    <i class="fa-solid fa-triangle-exclamation me-1"></i> Variance / Out of Balance
                                </td>
                                <td colspan="2" class="text-end text-warning-emphasis fw-bold">
                                    ₦ {{ number_format($diff, 2) }}
                                </td>
                            </tr>
                        @endif
                    </tfoot>
                </table>
            </div>
        </div>

        <div class="card-footer bg-light p-3 d-flex flex-column flex-sm-row justify-content-between align-items-center gap-2 small text-muted">
            <div>
                Source: Solar Foam Legacy ERP SQLite Archive
            </div>
            <div>
                Generated on: {{ now()->format('d-M-Y H:i:s') }}
            </div>
        </div>
    </div>
</div>
@endsection
