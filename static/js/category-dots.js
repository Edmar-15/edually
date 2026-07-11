// Assign subtle gradient colors to category dots based on slug
(function(){
    function hashStringToHue(s){
        let h = 0;
        for(let i=0;i<s.length;i++) h = (h<<5) - h + s.charCodeAt(i);
        return Math.abs(h) % 360;
    }

    document.addEventListener('DOMContentLoaded', function(){
        document.querySelectorAll('.cat-dot[data-slug]').forEach(function(dot){
            const slug = dot.getAttribute('data-slug') || '';
            const hue = hashStringToHue(slug || dot.nextElementSibling && dot.nextElementSibling.textContent || 'c');
            dot.style.background = `linear-gradient(180deg, hsl(${hue} 80% 88%), hsl(${(hue+15)%360} 70% 76%))`;
        });
    });
})();
