<script setup>
    import { ref, onMounted, onUnmounted } from 'vue';
    import RepositoryExplorer from './RepositoryExplorer.vue';
    import { defineExpose } from 'vue';

    const dialog = ref(null)
    const emit = defineEmits(['model-select'])
    const repositoryExplorer = ref(null);

    const props = defineProps(
    {
        title: 'footprint',
        filter: null,
    })

    const open = (parametr) =>
    {
        dialog.value.open = true
    };

    const handleKeydown = (e) =>
    {
        if (e.key === 'Escape' && dialog.value?.open)
        {
            dialog.value.open = false
        }
    };

    onMounted(() => window.addEventListener('keydown', handleKeydown))
    onUnmounted(() => window.removeEventListener('keydown', handleKeydown))

    // Library paths are stored relative to the repository root (symbols/ics/X.SchLib):
    // Altium resolves them against the folder holding the DbLib, which is the root of
    // the checked-out repository. The explorer's path starts with the repository's own
    // name, so that first segment must not end up in the stored path.
    const select = () =>
    {
        const selected = repositoryExplorer.value.getSelected()
        emit('model-select', { ...selected, path: selected.path.slice(1) })
        dialog.value.open = false
    }

    defineExpose({
        open
    });
</script>


<template>
    <onyks-dialog :title="`Select a ${props.title}`" corner-close bottom-buttons modal ref="dialog">
        <onyks-container type="stack" padding="" gap="l">
            <RepositoryExplorer :filter="props.filter" ref="repositoryExplorer"></RepositoryExplorer>
        </onyks-container>
        <onyks-button background="green" slot="footer" @click="select">OK</onyks-button>
        <onyks-button background="red" slot="footer" @click="dialog.open = false">Close</onyks-button>
    </onyks-dialog>
</template>

<style lang="css" scoped>
    onyks-dialog::part(container)
    {
        max-height: 80vh;
        height: fit-content;
    }

    onyks-dialog
    {
        position: fixed;
    }
</style>