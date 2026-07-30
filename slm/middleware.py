# slm/middleware.py
class NoCacheForDynamicPagesMiddleware:
    """
    Add Cache‑Control: no-store for every HTML response that is not a
    static asset.  This works together with the service‑worker network‑first
    strategy.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        # Only affect HTML responses (skip static, JSON, etc.)
        if response.get('Content-Type', '').startswith('text/html'):
            response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        return response
