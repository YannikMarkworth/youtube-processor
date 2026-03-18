/* ==============================================================================
   YouTube Processor – Browse JS
   Infinite scroll, live search, category chips, filter drawer, random discovery
   ============================================================================== */

(function () {
    "use strict";

    // --- State ---
    let currentPage = 1;
    let isLoading = false;
    let hasMore = true;
    let searchTimer = null;

    // --- DOM refs (set on DOMContentLoaded) ---
    let grid, sentinel, searchInput, filterDrawer;

    // --- Helpers ---

    function getFilterParams() {
        const params = new URLSearchParams();
        const q = searchInput ? searchInput.value.trim() : "";
        if (q) params.set("q", q);

        const playlist = document.getElementById("filter-playlist");
        const channel = document.getElementById("filter-channel");
        const sort = document.getElementById("filter-sort");

        if (playlist && playlist.value) params.set("playlist", playlist.value);
        if (channel && channel.value) params.set("channel", channel.value);
        if (sort && sort.value) {
            const parts = sort.value.split(":");
            params.set("sort", parts[0]);
            params.set("dir", parts[1] || "desc");
        }

        // Category from active chip
        const activeChip = document.querySelector(".chip.active[data-category]");
        if (activeChip && activeChip.dataset.category) {
            params.set("category", activeChip.dataset.category);
        }

        return params;
    }

    function createCardHTML(v) {
        const thumbSrc = v.video_id
            ? `https://img.youtube.com/vi/${v.video_id}/mqdefault.jpg`
            : "";
        const fallbackLetter = (v.title || "?")[0].toUpperCase();
        const duration = v.duration || "";
        const category = v.category || "";
        const channel = v.channel || "";
        const uploaded = v.uploaded || "";

        return `
        <a href="/video/${encodeURIComponent(v.id)}" class="video-card">
            <div class="card-thumbnail">
                ${thumbSrc
                    ? `<img loading="lazy" src="${thumbSrc}" alt="" onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';">`
                    : ""}
                <div class="card-thumbnail-fallback" style="${thumbSrc ? 'display:none' : 'display:flex'}">${fallbackLetter}</div>
                ${duration ? `<span class="card-duration">${duration}</span>` : ""}
            </div>
            <div class="card-body">
                <div class="card-title">${escapeHTML(v.title)}</div>
                <div class="card-meta">
                    <span class="channel-name">${escapeHTML(channel)}</span> · ${escapeHTML(uploaded)}
                </div>
                ${category ? `<span class="card-chip">${escapeHTML(category)}</span>` : ""}
            </div>
        </a>`;
    }

    function escapeHTML(str) {
        if (!str) return "";
        return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
                  .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
    }

    // --- Infinite Scroll ---

    async function loadNextPage() {
        if (isLoading || !hasMore) return;
        isLoading = true;

        currentPage++;
        const params = getFilterParams();
        params.set("page", currentPage);
        params.set("per_page", 48);

        try {
            const resp = await fetch(`/api/videos?${params.toString()}`);
            const data = await resp.json();

            if (data.videos && data.videos.length > 0) {
                const fragment = document.createDocumentFragment();
                const temp = document.createElement("div");
                data.videos.forEach(v => {
                    temp.innerHTML = createCardHTML(v);
                    fragment.appendChild(temp.firstElementChild);
                });
                grid.appendChild(fragment);
            }

            hasMore = data.has_next;
            if (!hasMore && sentinel) {
                sentinel.innerHTML = '<div class="load-end">Alle Videos geladen</div>';
            }
        } catch (err) {
            console.error("Failed to load next page:", err);
        }

        isLoading = false;
    }

    function setupInfiniteScroll() {
        sentinel = document.getElementById("scroll-sentinel");
        if (!sentinel) return;

        const observer = new IntersectionObserver(entries => {
            if (entries[0].isIntersecting) {
                loadNextPage();
            }
        }, { rootMargin: "200px" });

        observer.observe(sentinel);
    }

    // --- Reset & Reload Grid ---

    function resetAndReload() {
        currentPage = 1;
        hasMore = true;

        // Build new URL and navigate (server-renders page 1)
        const params = getFilterParams();
        window.location.href = "/?" + params.toString();
    }

    // --- Live Search ---

    function setupLiveSearch() {
        searchInput = document.getElementById("header-search");
        if (!searchInput) return;

        searchInput.addEventListener("input", () => {
            clearTimeout(searchTimer);
            searchTimer = setTimeout(() => {
                resetAndReload();
            }, 400);
        });

        // Enter key triggers immediately
        searchInput.addEventListener("keydown", (e) => {
            if (e.key === "Enter") {
                e.preventDefault();
                clearTimeout(searchTimer);
                resetAndReload();
            }
        });
    }

    // --- Category Chips ---

    function setupChips() {
        document.querySelectorAll(".chip[data-category]").forEach(chip => {
            chip.addEventListener("click", (e) => {
                e.preventDefault();
                // Toggle active state
                document.querySelectorAll(".chip[data-category]").forEach(c => c.classList.remove("active"));
                chip.classList.add("active");
                resetAndReload();
            });
        });
    }

    // --- Filter Drawer ---

    function setupFilterDrawer() {
        const toggleBtn = document.getElementById("filter-toggle");
        filterDrawer = document.getElementById("filter-drawer");
        if (!toggleBtn || !filterDrawer) return;

        toggleBtn.addEventListener("click", () => {
            filterDrawer.classList.toggle("open");
            toggleBtn.textContent = filterDrawer.classList.contains("open") ? "Filter ▲" : "Filter ▼";
        });

        // Apply filters on change
        filterDrawer.querySelectorAll("select").forEach(sel => {
            sel.addEventListener("change", () => {
                resetAndReload();
            });
        });
    }

    // --- Random Discovery ---

    async function loadRandomVideos() {
        const container = document.getElementById("random-grid");
        if (!container) return;

        try {
            const resp = await fetch("/api/random?n=4");
            const data = await resp.json();
            container.innerHTML = "";
            if (data.videos) {
                data.videos.forEach(v => {
                    container.insertAdjacentHTML("beforeend", createCardHTML(v));
                });
            }
        } catch (err) {
            console.error("Failed to load random videos:", err);
        }
    }

    function setupRandomButton() {
        const btn = document.getElementById("random-refresh");
        if (!btn) return;
        btn.addEventListener("click", (e) => {
            e.preventDefault();
            loadRandomVideos();
        });
    }

    // --- Init ---

    document.addEventListener("DOMContentLoaded", () => {
        grid = document.getElementById("video-grid");

        // Read hasMore from data attribute
        if (grid && grid.dataset.hasMore === "false") {
            hasMore = false;
        }

        setupLiveSearch();
        setupChips();
        setupFilterDrawer();
        setupInfiniteScroll();
        setupRandomButton();

        // Load random videos on initial page load
        if (document.getElementById("random-grid")) {
            loadRandomVideos();
        }
    });
})();
