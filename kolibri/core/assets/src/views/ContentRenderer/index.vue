<template>

  <div class="content-renderer">
    <UiAlert v-if="noRendererAvailable" :dismissible="false" type="error">
      {{ $tr('rendererNotAvailable') }}
    </UiAlert>
    <template v-else-if="available">
      <transition mode="out-in">
        <KCircularLoader
          v-if="!currentViewClass"
          :delay="false"
        />
        <component
          :is="currentViewClass"
          v-else
          ref="contentView"
          class="content-renderer-component"
          :files="availableFiles"
          :defaultFile="defaultFile"
          :itemId="itemId"
          :extraFields="extraFields"
          :answerState="answerState"
          :allowHints="allowHints"
          :supplementaryFiles="supplementaryFiles"
          :thumbnailFiles="thumbnailFiles"
          :interactive="interactive"
          :lang="lang"
          :showCorrectAnswer="showCorrectAnswer"
          @startTracking="startTracking"
          @stopTracking="stopTracking"
          @updateProgress="updateProgress"
          @updateContentState="updateContentState"
          @answerGiven="answerGiven"
          @hintTaken="hintTaken"
          @itemError="itemError"
          @interaction="interaction"
        />
      </transition>
    </template>
    <div v-else>
      {{ $tr('msgNotAvailable') }}
    </div>
  </div>

</template>


<script>

  import logger from 'kolibri.lib.logging';
  import heartbeat from 'kolibri.heartbeat';

  import UiAlert from 'keen-ui/src/UiAlert';
  import { defaultLanguage, languageValidator } from 'kolibri.utils.i18n';

  const logging = logger.getLogger(__filename);

  export default {
    name: 'ContentRenderer',
    components: {
      UiAlert,
    },
    props: {
      kind: {
        type: String,
        required: true,
      },
      files: {
        type: Array,
        default: () => [],
      },
      available: {
        type: Boolean,
        default: false,
      },
      assessment: {
        type: Boolean,
        default: false,
      },
      itemId: {
        type: String,
        default: null,
      },
      answerState: {
        type: Object,
        default: null,
      },
      allowHints: {
        type: Boolean,
        default: true,
      },
      extraFields: {
        type: Object,
        default: () => {},
      },
      initSession: {
        type: Function,
        default: () => Promise.resolve(),
      },
      // Allow content renderers to display in a static mode
      // where user interaction is not allowed
      interactive: {
        type: Boolean,
        default: true,
      },
      lang: {
        type: Object,
        default: () => defaultLanguage,
        validator: languageValidator,
      },
      showCorrectAnswer: {
        type: Boolean,
        default: false,
      },
    },
    data: () => ({
      currentViewClass: null,
      noRendererAvailable: false,
    }),
    computed: {
      extension() {
        if (this.availableFiles.length > 0) {
          return this.availableFiles[0].extension;
        }
        return undefined;
      },
      availableFiles() {
        return this.files.filter(
          file =>
            !file.thumbnail &&
            !file.supplementary &&
            file.available &&
            this.Kolibri.canRenderContent(this.kind, file.extension)
        );
      },
      defaultFile() {
        return this.availableFiles && this.availableFiles.length
          ? this.availableFiles[0]
          : undefined;
      },
      supplementaryFiles() {
        return this.files.filter(file => file.supplementary && file.available);
      },
      thumbnailFiles() {
        return this.files.filter(file => file.thumbnail && file.available);
      },
    },
    created() {
      this.updateRendererComponent();
      // This means this component has to be torn down on channel switches.
      this.$watch('files', this.updateRendererComponent);
    },
    methods: {
      /* Check the Kolibri core app for a content renderer module that is able to
       * handle the rendering of the current content node. This is the entrance point for changes
       * in the props,so any change in the props will trigger this function first.
       */
      updateRendererComponent() {
        // Assume we will find a renderer until we find out otherwise.
        this.noRendererAvailable = false;
        // Only bother to do this is if the node is available,
        // and the kind and extension are defined.
        // Otherwise the template can handle it.
        if (this.available && this.kind && this.extension) {
          return Promise.all([
            this.initSession(),
            this.Kolibri.retrieveContentRenderer(this.kind, this.extension),
          ])
            .then(([session, component]) => {
              this.$emit('sessionInitialized', session);
              this.currentViewClass = component;
              return this.currentViewClass;
            })
            .catch(error => {
              logging.error(error);
              this.noRendererAvailable = true;
            });
        }
        return Promise.resolve(null);
      },
      answerGiven(...args) {
        this.$emit('answerGiven', ...args);
        heartbeat.setUserActive();
      },
      hintTaken(...args) {
        this.$emit('hintTaken', ...args);
        heartbeat.setUserActive();
      },
      itemError(...args) {
        this.$emit('itemError', ...args);
        heartbeat.setUserActive();
      },
      interaction(...args) {
        this.$emit('interaction', ...args);
        heartbeat.setUserActive();
      },
      updateProgress(...args) {
        this.$emit('updateProgress', ...args);
        heartbeat.setUserActive();
      },
      updateContentState(...args) {
        this.$emit('updateContentState', ...args);
        heartbeat.setUserActive();
      },
      startTracking(...args) {
        this.$emit('startTracking', ...args);
        heartbeat.setUserActive();
      },
      stopTracking(...args) {
        this.$emit('stopTracking', ...args);
      },
      /**
       * @public
       */
      checkAnswer() {
        if (this.assessment && this.$refs.contentView && this.$refs.contentView.checkAnswer) {
          return this.$refs.contentView.checkAnswer();
        } else if (!this.assessment) {
          logging.warn('Checking answer of something that is not an assessment');
        } else if (!this.$refs.contentView) {
          logging.warn('No content view to check answer of');
        } else if (!this.$refs.contentView.checkAnswer) {
          logging.warn('This content renderer has not implemented the checkAnswer method');
        }
        heartbeat.setUserActive();
        return null;
      },
    },
    $trs: {
      msgNotAvailable: 'This content is not available',
      rendererNotAvailable: 'Kolibri is unable to render this content',
    },
  };

</script>


<style lang="scss" scoped></style>
