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

    defineExpose({
        open
    });
</script>


<template>
    <onyks-dialog :title="`Select a ${props.title}`" corner-close bottom-buttons modal ref="dialog">
        <onyks-container type="stack" padding="" gap="l">
            <RepositoryExplorer :filter="props.filter" ref="repositoryExplorer"></RepositoryExplorer>
        </onyks-container>
        <onyks-button background="green" slot="footer" @click="emit('model-select', repositoryExplorer.getSelected()); dialog.open = false">OK</onyks-button>
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