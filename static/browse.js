/* ==============================================================================
   MyTube – Browse JS
   Sidebar, infinite scroll, live search, filter drawer, chips, random discovery
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

    // --- Duration helpers ---

    function parseDurationSecs(d) {
        if (!d) return 0;
        const parts = d.split(":").map(Number);
        if (parts.length === 3) return parts[0] * 3600 + parts[1] * 60 + parts[2];
        if (parts.length === 2) return parts[0] * 60 + parts[1];
        return 0;
    }

    function isShort(duration) {
        return parseDurationSecs(duration) < 90;
    }

    // --- Helpers ---

    function escapeHTML(str) {
        if (!str) return "";
        return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
                  .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
    }

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

        // Read category/subcategory/topic from current URL
        const urlParams = new URLSearchParams(window.location.search);
        if (urlParams.get("category")) params.set("category", urlParams.get("category"));
        if (urlParams.get("subcategory")) params.set("subcategory", urlParams.get("subcategory"));
        if (urlParams.get("topic")) params.set("topic", urlParams.get("topic"));

        // Length filter from active chip
        const activeChip = document.querySelector(".chip.active[data-length]");
        if (activeChip && activeChip.dataset.length !== "all") {
            params.set("length", activeChip.dataset.length);
        }

        return params;
    }

    function createCardHTML(v) {
        const short = v.is_short || isShort(v.duration);
        const thumbSrc = v.video_id
            ? `https://img.youtube.com/vi/${v.video_id}/maxresdefault.jpg`
            : "";
        const fallbackLetter = (v.title || "?")[0].toUpperCase();
        const duration = v.duration || "";
        const channel = v.channel || "";
        const uploaded = v.uploaded || "";
        const tldr = v.tldr || "";
        const category = v.category || "";

        const thumbClass = short ? "card-thumbnail is-short" : "card-thumbnail";
        const fallbackStyle = thumbSrc ? ' style="display:none"' : '';

        return `
        <a href="/video/${encodeURIComponent(v.id)}" class="video-card">
            <div class="${thumbClass}">
                ${thumbSrc
                    ? `<img loading="lazy" src="${thumbSrc}" alt=""
                            onerror="this.src='https://img.youtube.com/vi/${v.video_id}/hqdefault.jpg'">`
                    : ""}
                <div class="card-thumbnail-fallback"${fallbackStyle}>${fallbackLetter}</div>
                ${short ? '<span class="shorts-badge">Short</span>' : ""}
                ${duration ? `<span class="card-duration">${escapeHTML(duration)}</span>` : ""}
            </div>
            <div class="card-body">
                <div class="card-title">${escapeHTML(v.title)}</div>
                <div class="card-meta">
                    <span class="channel-name">${escapeHTML(channel)}</span>${uploaded ? ` · ${escapeHTML(uploaded)}` : ""}
                </div>
                ${category ? `<span class="card-chip">${escapeHTML(category)}</span>` : ""}
                ${tldr ? `<div class="card-tldr">${escapeHTML(tldr)}</div>` : ""}
            </div>
        </a>`;
    }

    // --- Sidebar ---

    function setupSidebar() {
        const sidebar = document.getElementById("sidebar");
        const toggleBtn = document.getElementById("sidebar-toggle");
        const overlay = document.getElementById("sidebar-overlay");
        if (!sidebar || !toggleBtn) return;

        // Restore state from localStorage (desktop only)
        const savedState = localStorage.getItem("sidebar-collapsed");
        if (savedState === "true" && window.innerWidth > 1024) {
            sidebar.classList.add("collapsed");
        }

        toggleBtn.addEventListener("click", () => {
            if (window.innerWidth <= 1024) {
                // Mobile: toggle overlay mode
                sidebar.classList.toggle("mobile-open");
                if (overlay) overlay.classList.toggle("visible");
            } else {
                // Desktop: collapse/expand
                sidebar.classList.toggle("collapsed");
                // Push main content when collapsed
                const main = document.querySelector(".main-content");
                if (main) main.style.marginLeft = sidebar.classList.contains("collapsed") ? "0" : "";
                localStorage.setItem("sidebar-collapsed", sidebar.classList.contains("collapsed"));
            }
        });

        // Close sidebar on overlay click (mobile)
        if (overlay) {
            overlay.addEventListener("click", () => {
                sidebar.classList.remove("mobile-open");
                overlay.classList.remove("visible");
            });
        }

        // Apply saved collapse state on desktop
        if (savedState === "true" && window.innerWidth > 1024) {
            const main = document.querySelector(".main-content");
            if (main) main.style.marginLeft = "0";
        }
    }

    // --- Category Tree ---

    function setupCategoryTree() {
        document.querySelectorAll(".sidebar-expand-btn").forEach(btn => {
            const header = btn.closest(".sidebar-cat-header, .sidebar-sub-header");
            if (!header) return;
            const target = header.nextElementSibling;

            btn.addEventListener("click", (e) => {
                e.preventDefault();
                e.stopPropagation();
                if (!target) return;

                const isHidden = target.style.display === "none";
                target.style.display = isHidden ? "" : "none";
                btn.classList.toggle("expanded", isHidden);

                saveSidebarTreeState();
            });
        });

        restoreSidebarTreeState();
    }

    function saveSidebarTreeState() {
        const expanded = [];
        document.querySelectorAll(".sidebar-expand-btn.expanded").forEach(btn => {
            const header = btn.closest(".sidebar-cat-header, .sidebar-sub-header");
            if (header) {
                const cat = header.dataset.category || header.dataset.subcategory || "";
                if (cat) expanded.push(cat);
            }
        });
        localStorage.setItem("sidebar-tree-expanded", JSON.stringify(expanded));
    }

    function restoreSidebarTreeState() {
        try {
            const expanded = JSON.parse(localStorage.getItem("sidebar-tree-expanded") || "[]");
            if (!expanded.length) return;

            document.querySelectorAll(".sidebar-cat-header, .sidebar-sub-header").forEach(header => {
                const key = header.dataset.category || header.dataset.subcategory || "";
                if (key && expanded.includes(key)) {
                    const btn = header.querySelector(".sidebar-expand-btn");
                    const target = header.nextElementSibling;
                    if (btn && target) {
                        target.style.display = "";
                        btn.classList.add("expanded");
                    }
                }
            });
        } catch (e) {
            // Ignore invalid localStorage data
        }
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
        }, { rootMargin: "300px" });

        observer.observe(sentinel);
    }

    // --- Reset & Reload Grid ---

    function resetAndReload() {
        currentPage = 1;
        hasMore = true;

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

        searchInput.addEventListener("keydown", (e) => {
            if (e.key === "Enter") {
                e.preventDefault();
                clearTimeout(searchTimer);
                resetAndReload();
            }
        });
    }

    // --- Filter Drawer ---

    function setupFilterDrawer() {
        const toggleBtn = document.getElementById("filter-toggle");
        filterDrawer = document.getElementById("filter-drawer");
        if (!toggleBtn || !filterDrawer) return;

        toggleBtn.addEventListener("click", () => {
            filterDrawer.classList.toggle("open");
            toggleBtn.textContent = filterDrawer.classList.contains("open") ? "Filter \u25B2" : "Filter \u25BC";
        });

        filterDrawer.querySelectorAll("select").forEach(sel => {
            sel.addEventListener("change", () => {
                resetAndReload();
            });
        });
    }

    // --- Length Filter Chips ---

    function setupChips() {
        // Restore active chip from URL
        const urlParams = new URLSearchParams(window.location.search);
        const activeLength = urlParams.get("length") || "all";
        document.querySelectorAll(".chip[data-length]").forEach(chip => {
            chip.classList.toggle("active", chip.dataset.length === activeLength);
        });

        document.querySelectorAll(".chip[data-length]").forEach(chip => {
            chip.addEventListener("click", () => {
                document.querySelectorAll(".chip[data-length]").forEach(c => c.classList.remove("active"));
                chip.classList.add("active");
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

        if (grid && grid.dataset.hasMore === "false") {
            hasMore = false;
        }

        setupSidebar();
        setupCategoryTree();
        setupLiveSearch();
        setupFilterDrawer();
        setupChips();
        setupInfiniteScroll();
        setupRandomButton();

        // Load random videos on initial page load
        if (document.getElementById("random-grid")) {
            loadRandomVideos();
        }
    });
})();
