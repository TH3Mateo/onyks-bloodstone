<script setup lang="js">
    import { onMounted } from 'vue';
    import { ref } from 'vue';
    import { repository } from '@/utils/api';
    import { defineExpose } from 'vue';

    const path = ref(null)
    const explorer = ref(null)
    const props = defineProps(
    {
        filter:
        {
            type: Function,
            required: false,
            default: () => (e) =>
            {
                return true
            }
        },
        // Top-level folder of the repository the explorer starts in and cannot leave
        // (e.g. 'symbols'). The path shown is relative to the repository root, so it
        // can be stored as-is.
        root:
        {
            type: String,
            required: true
        }
    })

    const load = async () =>
    {
        let temp = Array.from((await repository.list(path.value.content.join('/'))).data)
        temp = temp.filter(e => props.filter(e))
        explorer.value.content = temp
    }

    const pathChange = async (e) =>
    {
        if (path.value.content.length == 0)
        {
            path.value.content = [props.root]
        }
        await load()
    }

    const enterFolder = async (e) =>
    {
        path.value.content = [...path.value.content, e.detail.folder.name]
        await load()
    }

    const refresh = async () =>
    {
        await load()
    }

    const getSelected = (parametr) =>
    {
        return {path: [...path.value.content], item: explorer.value.getSelectedItems()[0] ?? null}
    };

    defineExpose(
    {
        getSelected
    });

    onMounted(async () =>
    {
        explorer.value.types = [{type: 'file', icon: 'F390', isLikeDir: false},
        {type: 'dir', icon: 'F3D8', isLikeDir: true},
        {type: 'schlib', icon: 'F3D5', isLikeDir: true},
        {type: 'pcblib', icon: 'F3D5', isLikeDir: true},
        {type: 'footprint', icon: 'F6E7', isLikeDir: false},
        {type: 'symbol', icon: 'F6E2', isLikeDir: false}]

        path.value.content = [props.root]
        await load()
    })
</script>

<template>
    <onyks-path ref="path" @path-change="pathChange"></onyks-path>
    <onyks-file-explorer ref="explorer" @enter-folder="enterFolder"></onyks-file-explorer>
    <onyks-container type="group" padding="" justify="end">
        <onyks-button @click="refresh" background="green">Refresh</onyks-button>
    </onyks-container>
</template>

<style lang="css" scoped>
    onyks-file-explorer
    {
        width: 100%;
        height: 200px;
    }

    onyks-button
    {
        width: 120px;
    }
</style>
