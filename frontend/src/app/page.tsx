import Link from 'next/link';

export default function LandingPage() {
  return (
    <div className="bg-white text-slate-900 min-h-screen flex flex-col justify-between font-sans selection:bg-indigo-600 selection:text-white">
      {/* Top Navigation */}
      <header className="max-w-7xl mx-auto w-full px-6 lg:px-8 h-20 flex items-center justify-between border-b border-slate-100">
        <div className="flex items-center space-x-2">
          <span className="text-2xl font-extrabold text-slate-900">
            Phone<span className="text-indigo-600">ERP</span>
          </span>
        </div>
        <div className="flex items-center space-x-4">
          <Link href="/login" className="text-sm font-semibold text-slate-600 hover:text-indigo-600 transition-colors">
            Sign in
          </Link>
          <Link href="/signup" className="text-sm font-semibold bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-lg transition-colors shadow-sm shadow-indigo-105">
            Get Started
          </Link>
        </div>
      </header>

      {/* Hero Section */}
      <main className="flex-1 max-w-7xl mx-auto w-full px-6 lg:px-8 py-20 flex flex-col justify-center text-center">
        <div className="max-w-3xl mx-auto">
          <h1 className="text-5xl md:text-6xl font-extrabold tracking-tight text-slate-900 leading-tight">
            Automate Phone Orders using <span className="text-indigo-600">AI Intelligence</span>
          </h1>
          <p className="mt-6 text-lg text-slate-600 leading-relaxed">
            Eliminate manual data entry. PhoneERP transcribes customer order calls, extracts line items, quantities, addresses, and delivery requirements using AI, and loads them directly into your verification pipeline.
          </p>
          <div className="mt-10 flex flex-col sm:flex-row items-center justify-center gap-4">
            <Link href="/signup" className="w-full sm:w-auto text-center font-bold bg-indigo-600 hover:bg-indigo-700 text-white px-8 py-4 rounded-xl transition-all shadow-md shadow-indigo-100 text-base">
              Start Your Free Trial
            </Link>
            <Link href="/login" className="w-full sm:w-auto text-center font-bold bg-slate-50 hover:bg-slate-100 text-slate-700 border border-slate-200 px-8 py-4 rounded-xl transition-all text-base">
              Access Dashboard
            </Link>
          </div>
        </div>

        {/* Feature Grid */}
        <div className="mt-24 grid grid-cols-1 md:grid-cols-3 gap-8">
          <div className="p-8 rounded-2xl border border-slate-200 bg-slate-50 text-left shadow-sm">
            <div className="h-10 w-10 bg-indigo-50 text-indigo-700 border border-indigo-200 rounded-lg flex items-center justify-center font-bold text-lg mb-6">
              1
            </div>
            <h3 className="text-lg font-bold text-slate-900 mb-2">Voice Transcription</h3>
            <p className="text-sm text-slate-600 leading-relaxed">
              Upload customer voicemail transcripts or record audio streams. Converts speech into precise text.
            </p>
          </div>

          <div className="p-8 rounded-2xl border border-slate-200 bg-slate-50 text-left shadow-sm">
            <div className="h-10 w-10 bg-indigo-50 text-indigo-700 border border-indigo-200 rounded-lg flex items-center justify-center font-bold text-lg mb-6">
              2
            </div>
            <h3 className="text-lg font-bold text-slate-900 mb-2">AI Entity Extraction</h3>
            <p className="text-sm text-slate-600 leading-relaxed">
              Google Gemini parses raw voice logs to extract customers, phone numbers, items, quantities, and delivery coordinates automatically.
            </p>
          </div>

          <div className="p-8 rounded-2xl border border-slate-200 bg-slate-50 text-left shadow-sm">
            <div className="h-10 w-10 bg-indigo-50 text-indigo-700 border border-indigo-200 rounded-lg flex items-center justify-center font-bold text-lg mb-6">
              3
            </div>
            <h3 className="text-lg font-bold text-slate-900 mb-2">Review & Confirm</h3>
            <p className="text-sm text-slate-600 leading-relaxed">
              View extracted details inside structured Action Cards. Verify items, make edits, and approve straight into the order queue.
            </p>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="max-w-7xl mx-auto w-full px-6 lg:px-8 py-8 border-t border-slate-100 text-center text-xs text-slate-450 font-medium">
        &copy; {new Date().getFullYear()} PhoneERP Inc. All rights reserved.
      </footer>
    </div>
  );
}
