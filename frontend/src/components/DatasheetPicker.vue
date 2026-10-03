<script setup>
    import { ref } from 'vue';
    import { defineEmits } from 'vue';

    const props = defineProps(['type', 'datasheet'])
    const uploader = ref(null)

    const emit = defineEmits(['change'])

    const mode = defineModel('mode', {default: 2})
    const file = defineModel('file', {default: null})

    console.log(props.data)
</script>

<template>
    
    <template v-if="props.datasheet && props.type == 'duplicate'">
        <onyks-container type="group" justify="left" align="center" >
            <onyks-checkbox :checked="mode == 0" @click="(e) => {mode == 0? e.preventDefault():mode = 0}"></onyks-checkbox>
            <onyks-text>Copy datasheet from the duplicated element</onyks-text>
        </onyks-container>

        <onyks-container type="group" justify="left" align="center" v-if="props.datasheet">
            <onyks-checkbox :checked="mode == 1" @click="(e) => {mode == 1? e.preventDefault():mode = 1}"></onyks-checkbox>
            <onyks-text>Duplicate element without datasheet</onyks-text>
        </onyks-container>

        <onyks-container type="group" justify="left" align="center" v-if="props.datasheet">
            <onyks-checkbox :checked="mode == 2" @click="(e) => {mode == 2? e.preventDefault():mode = 2}"></onyks-checkbox>
            <onyks-text>Replace datasheet by a new one</onyks-text>
        </onyks-container>
    </template>

    <template v-if="props.datasheet && props.type == 'edit'">

        <onyks-container type="group" justify="left" align="center" >
            <onyks-checkbox :checked="mode == 0" @click="(e) => {mode == 0? e.preventDefault():mode = 0}"></onyks-checkbox>
            <onyks-text>Don't change the datasheet</onyks-text>
        </onyks-container>

        <onyks-container type="group" justify="left" align="center" >
            <onyks-checkbox :checked="mode == 1" @click="(e) => {mode == 1? e.preventDefault():mode = 1}"></onyks-checkbox>
            <onyks-text>Remove current datasheet</onyks-text>
        </onyks-container>

        <onyks-container type="group" justify="left" align="center" v-if="props.datasheet">
            <onyks-checkbox :checked="mode == 2" @click="(e) => {mode == 2? e.preventDefault():mode = 2}"></onyks-checkbox>
            <onyks-text>Replace datasheet by a new one</onyks-text>
        </onyks-container>
    </template>

    <onyks-file-upload ref="uploader" accept=".pdf" message="Drag a file or click to add it" @change="file = uploader.files[0]" :disabled="mode != 2 && props.type != 'add' && !(props.type == 'edit' && !props.datasheet)"></onyks-file-upload>
    <onyks-container type="group">
        <onyks-button @click="uploader.reset">Reset</onyks-button>
    </onyks-container>
</template>

<style scoped>
    onyks-file-upload
    {
        width: 100%;
    }
</style>