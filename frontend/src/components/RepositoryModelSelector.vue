<script setup>
    import { ref, onMounted, onUnmounted } from 'vue';
    import RepositoryExplorer from './RepositoryExplorer.vue';
    import { defineExpose } from 'vue';

    const dialog = ref(null)
    const emit = defineEmits(['model-select'])
    const repositoryExplorer = ref(null);
    const error = ref('')

    const props = defineProps(
    {
        title: { type: String, default: 'footprint' },
        filter: { type: Function, default: null },
        // Repository folder the explorer starts in: 'symbols' or 'footprints'.
        root: { type: String, required: true },
        // Type of the explorer item that completes the selection: 'symbol' or 'footprint'.
        leafType: { type: String, required: true },
    })

    const open = (parametr) =>
    {
        error.value = ''
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
    // the checked-out repository. The explorer starts in props.root, so its path already
    // has that form. A selection is only complete once a symbol/footprint inside a
    // library file is picked - a bare folder or library file is rejected.
    const select = () =>
    {
        const { path, item } = repositoryExplorer.value.getSelected()
        if (item?.type !== props.leafType)
        {
            error.value = `Open a library file and select a ${props.leafType} inside it.`
            return
        }
        emit('model-select', { name: item.name, path })
        dialog.value.open = false
    }

    defineExpose({
        open
    });
</script>


<template>
    <onyks-dialog :title="`Select a ${props.title}`" corner-close bottom-buttons modal ref="dialog">
        <onyks-container type="stack" padding="" gap="l">
            <RepositoryExplorer :filter="props.filter" :root="props.root" ref="repositoryExplorer"></RepositoryExplorer>
            <onyks-text v-if="error">{{ error }}</onyks-text>
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
