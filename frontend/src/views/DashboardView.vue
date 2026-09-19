<script setup lang="js">
    // Layout restored from the Flask-era dashboard (commit d858152): one large card with
    // the element totals, two small cards with repository symbol/footprint counts, and a
    // tile per component category underneath.
    import WarningAlert from '@/components/WarningAlert.vue';
    import { onMounted, onUnmounted, ref } from 'vue';
    import { element, repository, table } from '@/utils/api';

    const LOADING = '…'
    const FAILED = '—'

    const elements = ref(LOADING)
    const elementsToday = ref(LOADING)
    const lastAdded = ref(null)
    const repositoryStatistics = ref({ symbols: LOADING, footprints: LOADING })
    const categories = ref({})

    const valueOr = (response, fallback) => response?.status == 200 ? response.data : fallback

    const startOfToday = () =>
    {
        const now = new Date()
        return new Date(now.getFullYear(), now.getMonth(), now.getDate())
    }

    const updateDatabase = async () =>
    {
        const [total, today, last, perCategory] = await Promise.all([
            element.number(),
            element.number(startOfToday()),
            element.lastAdded(),
            table.numbers(),
        ])
        elements.value = valueOr(total, FAILED)
        elementsToday.value = valueOr(today, FAILED)
        // 404 means the database is simply empty.
        lastAdded.value = valueOr(last, null)
        categories.value = valueOr(perCategory, categories.value)
    }

    // Counting symbols/footprints parses every library file on the first call after a
    // commit, so a slow request must not be stacked with another one.
    let repositoryPending = false
    const updateRepository = async () =>
    {
        if (repositoryPending)
        {
            return
        }
        repositoryPending = true
        const response = await repository.statistics()
        repositoryPending = false
        repositoryStatistics.value = valueOr(response, { symbols: FAILED, footprints: FAILED })
    }

    const update = () =>
    {
        updateDatabase()
        updateRepository()
    }

    let updateInterval = null

    onMounted(() =>
    {
        update()
        updateInterval = setInterval(update, 5000)
    })

    onUnmounted(() => clearInterval(updateInterval))
</script>

<template>
    <onyks-container gap="l" padding="l">

        <onyks-header>Dashboard</onyks-header>

        <WarningAlert></WarningAlert>

        <div class="dashboard-grid">

            <div class="card large-card">
                <h2>Collected elements</h2>
                <div class="stat-number">{{ elements }}</div>
                <p class="stat-label">Total number of elements</p>
                <p><strong>New today: </strong>{{ elementsToday }}</p>
                <p>
                    <strong>Last added: </strong>
                    <router-link v-if="lastAdded" :to="`/element/details/${lastAdded.uuid}`">
                        {{ lastAdded.partName }}
                    </router-link>
                    <span v-else>None</span>
                    <span v-if="lastAdded" class="muted"> ({{ lastAdded.table }})</span>
                </p>
            </div>

            <div class="small-cards">
                <div class="card small-card">
                    <h2>Footprints</h2>
                    <div class="stat-number">{{ repositoryStatistics.footprints }}</div>
                    <p class="stat-label">Available footprints</p>
                </div>
                <div class="card small-card">
                    <h2>Symbols</h2>
                    <div class="stat-number">{{ repositoryStatistics.symbols }}</div>
                    <p class="stat-label">Available symbols</p>
                </div>
            </div>

            <div class="categories-grid">
                <div v-for="(count, name) in categories" :key="name" class="card category-card">
                    <h3>{{ name }}</h3>
                    <div class="category-stat">{{ count }}</div>
                </div>
                <p v-if="Object.keys(categories).length === 0" class="muted">There are no categories yet.</p>
            </div>

        </div>

    </onyks-container>
</template>

<style scoped>
    .dashboard-grid
    {
        display: grid;
        grid-template-columns: 1fr 1fr;
        grid-template-areas: "large small" "categories categories";
        gap: var(--onyks-spacing-md);
        width: 100%;
        font-family: var(--onyks-font);
        color: var(--onyks-on-surface-1);
    }

    .card
    {
        background-color: var(--onyks-surface-1);
        border: 1px solid var(--onyks-surface-1-border);
        border-radius: var(--onyks-radius-lg);
        box-sizing: border-box;
        transition: all 0.4s cubic-bezier(0.25, 0.8, 0.25, 1);
    }

    .large-card, .small-card
    {
        padding: 2rem;
    }

    .large-card:hover, .small-card:hover
    {
        transform: translateY(-8px);
        box-shadow: 0 1rem 2rem var(--onyks-surface-1-border);
        border-color: var(--onyks-accent);
    }

    .large-card
    {
        grid-area: large;
        min-height: 300px;
    }

    .small-cards
    {
        grid-area: small;
        display: grid;
        grid-template-rows: 1fr 1fr;
        gap: var(--onyks-spacing-md);
    }

    h2
    {
        font-size: 1.5rem;
        color: var(--onyks-accent);
        font-weight: 600;
        margin: 0 0 24px 0;
        padding-bottom: 12px;
        position: relative;
    }

    h2::after
    {
        content: '';
        position: absolute;
        left: 0;
        bottom: 0;
        width: 48px;
        height: 2px;
        background-color: var(--onyks-accent);
    }

    .stat-number
    {
        font-size: 4rem;
        font-weight: bold;
        line-height: 1;
        margin: 1rem 0;
    }

    .small-card .stat-number
    {
        font-size: 2.5rem;
    }

    .stat-label
    {
        font-size: 1.2rem;
        opacity: 0.7;
        margin: 0 0 0.5rem 0;
    }

    .muted
    {
        opacity: 0.7;
    }

    a
    {
        color: var(--onyks-accent);
    }

    .categories-grid
    {
        grid-area: categories;
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        gap: var(--onyks-spacing-md);
    }

    .category-card
    {
        padding: 1.5rem;
        text-align: center;
    }

    .category-card:hover
    {
        transform: translateY(-5px);
        box-shadow: 0 0.5rem 1rem var(--onyks-surface-1-border);
        border-color: var(--onyks-accent);
    }

    h3
    {
        font-size: 1.1rem;
        color: var(--onyks-accent);
        font-weight: 600;
        margin: 0 0 1rem 0;
        overflow-wrap: anywhere;
    }

    .category-stat
    {
        font-size: 2.5rem;
        font-weight: bold;
        line-height: 1;
        margin: 0.5rem 0;
    }

    @media (max-width: 900px)
    {
        .dashboard-grid
        {
            grid-template-columns: 1fr;
            grid-template-areas: "large" "small" "categories";
        }

        .categories-grid
        {
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
        }
    }
</style>
