<?php

namespace App\Http\Controllers;

use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;

class GeneralLedgerController extends Controller
{
    public function index(Request $request)
    {
        $query = DB::table('gl_accounts');

        if ($request->filled('search')) {
            $q = '%' . $request->search . '%';
            $query->where(function ($qb) use ($q) {
                $qb->where('account_code', 'like', $q)
                   ->orWhere('account_name', 'like', $q)
                   ->orWhere('account_type', 'like', $q)
                   ->orWhere('account_group', 'like', $q);
            });
        }

        $accounts = $query->orderBy('account_code')->paginate(80)->withQueryString();

        return view('gl.index', compact('accounts'));
    }

    public function show(Request $request, string $code)
    {
        $account = DB::table('gl_accounts')->where('account_code', $code)->first();

        if (!$account) {
            abort(404, 'GL Account not found.');
        }

        $hasInquiry = Schema::hasTable('gl_account_inquiry_lines');
        $useInquiry = $hasInquiry
            && DB::table('gl_account_inquiry_lines')->where('account_code', $code)->exists();

        if ($useInquiry) {
            $transQuery = DB::table('gl_account_inquiry_lines')
                ->where('account_code', $code)
                ->orderBy('trans_date', 'asc')
                ->orderBy('trans_no', 'asc')
                ->orderBy('id', 'asc');

            if ($request->filled('from_date')) {
                $transQuery->where('trans_date', '>=', $request->from_date);
            }
            if ($request->filled('to_date')) {
                $transQuery->where('trans_date', '<=', $request->to_date);
            }

            $transactions = $transQuery->paginate(100)->withQueryString();

            return view('gl.show', [
                'account' => $account,
                'transactions' => $transactions,
                'ledgerSource' => 'inquiry',
            ]);
        }

        $transQuery = DB::table('gl_transactions')
            ->where('account_code', $code)
            ->orderBy('trans_date', 'desc')
            ->orderBy('id', 'desc');

        if ($request->filled('from_date')) {
            $transQuery->where('trans_date', '>=', $request->from_date);
        }
        if ($request->filled('to_date')) {
            $transQuery->where('trans_date', '<=', $request->to_date);
        }

        $transactions = $transQuery->paginate(100)->withQueryString();

        return view('gl.show', [
            'account' => $account,
            'transactions' => $transactions,
            'ledgerSource' => 'journal',
        ]);
    }

    public function trialBalance()
    {
        $accounts = DB::table('gl_accounts')
            ->select('account_code', 'account_name', 'account_type', 'account_group', 'balance')
            ->orderBy('account_code')
            ->get();

        return view('gl.trial_balance', compact('accounts'));
    }
}
