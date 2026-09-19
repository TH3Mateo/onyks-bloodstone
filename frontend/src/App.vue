<script setup>
    import { useRoute } from 'vue-router'
    import { ref, provide } from 'vue'
    import { readStorage, writeStorage } from '@/utils/storage.js'
    const route = useRoute()

    const fullWidth = ref(readStorage('onyks-full-width', false))
    const toggleFullWidth = () =>
    {
        fullWidth.value = !fullWidth.value
        writeStorage('onyks-full-width', fullWidth.value)
    }
    provide('fullWidth', fullWidth)
    provide('toggleFullWidth', toggleFullWidth)
</script>

<template>
    <onyks-nav size="m" mobile-breakpoint="900" max-view-items="5">
        <img src="../node_modules/onyks-web-ui-system/dist/logo.png" class="logo">
        <router-link slot="nav" to="/dashboard" .selected="route.path.endsWith('/dashboard')">Dashboard</router-link>
        <router-link slot="nav" to="/management" .selected="route.path.endsWith('/management')">Management</router-link>
        <router-link slot="nav" to="/repository" .selected="route.path.endsWith('/repository')">Repository</router-link>
        <router-link slot="nav" to="/settings" .selected="route.path.endsWith('/settings')">Settings</router-link>
    </onyks-nav>
    <main :class="{ 'full-width': fullWidth }">
        <router-view v-slot="{ Component, route }">
            <transition name="fade" mode="out-in">
                <div :key="route.path">
                    <component :is="Component" />
                </div>
            </transition>
        </router-view>
    </main>
    <footer></footer>
</template>

<style lang="css" scoped>
    .logo
    {
        height: 100%;
        padding: var(--onyks-spacing-md);
        box-sizing: border-box;
        position: absolute;
    }
</style>

<style lang="css">
    onyks-button
    {
        width: 140px;
    }

    onyks-nav
    {
        position: sticky;
        top: 0;
        margin: 0;
        width: auto;
        z-index: 12;
    }

    main
    {
        max-width: 1024px;
        margin-left: auto;
        margin-right: auto;
        min-height: 100vh;
        box-sizing: border-box;
        transition: max-width 0.2s ease;
    }

    main.full-width
    {
        max-width: none;
        padding-left: var(--onyks-spacing-lg);
        padding-right: var(--onyks-spacing-lg);
    }

    footer
    {
        height: 300px;
        width: 100%;
        padding: var(--onyks-spacing-lg);
        background-color: var(--onyks-surface-1);
        box-sizing: border-box;
    }

    .fade-enter-active, .fade-leave-active 
    {
        transition: opacity 0.2s ease;
    }

    .fade-enter-from, .fade-leave-to 
    {
        opacity: 0;
    }

    onyks-dialog
    {
        z-index: 20;
        position: relative;
    }
</style>