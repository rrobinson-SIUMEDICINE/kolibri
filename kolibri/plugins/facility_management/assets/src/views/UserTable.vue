<template>

  <div>
    <CoreTable>

      <thead slot="thead">
        <tr>
          <th
            v-if="selectable"
            class="core-table-checkbox-col select-all"
          >
            <KCheckbox
              :label="selectAllLabel"
              :showLabel="true"
              :checked="allAreSelected"
              class="overflow-label"
              :disabled="users.length === 0"
              @change="selectAll($event)"
            />
          </th>
          <th>
            <!-- "Full name" header visually hidden if checkbox is on -->
            <span :class="{visuallyhidden: selectable}">
              {{ coreString('fullNameLabel') }}
            </span>
          </th>
          <th>
            <span class="visuallyhidden">
              {{ $tr('role') }}
            </span>
          </th>
          <th>{{ coreString('usernameLabel') }}</th>
          <th v-if="$scopedSlots.info">
            {{ infoDescriptor }}
          </th>
          <th v-if="$scopedSlots.action" class="user-action-button">
            <span class="visuallyhidden">
              {{ $tr('userActionsColumnHeader') }}
            </span>
          </th>
        </tr>
      </thead>

      <tbody slot="tbody">
        <tr
          v-for="user in users"
          :key="user.id"
        >
          <td v-if="selectable" class="core-table-checkbox-col">
            <KCheckbox
              :label="userCheckboxLabel"
              :showLabel="false"
              :checked="userIsSelected(user.id)"
              @change="selectUser(user.id, $event)"
            />
          </td>
          <td>
            <KLabeledIcon :icon="isCoach ? 'coach' : 'person'" :label="user.full_name" />
            <UserTypeDisplay
              aria-hidden="true"
              :userType="user.kind"
              :omitLearner="true"
              class="role-badge"
              :style="{
                color: $themeTokens.textInverted,
                backgroundColor: $themeTokens.annotation,
              }"
            />
          </td>
          <td class="visuallyhidden">
            {{ user.kind }}
          </td>
          <td>
            <span dir="auto">
              {{ user.username }}
            </span>
          </td>
          <td v-if="$scopedSlots.info">
            <slot name="info" :user="user"></slot>
          </td>
          <td v-if="$scopedSlots.action" class="core-table-button-col">
            <slot name="action" :user="user"></slot>
          </td>
        </tr>
      </tbody>
    </CoreTable>

    <p
      v-if="!users.length"
      class="empty-message"
    >
      {{ emptyMessage }}
    </p>

  </div>

</template>


<script>

  import UserTypeDisplay from 'kolibri.coreVue.components.UserTypeDisplay';
  import CoreTable from 'kolibri.coreVue.components.CoreTable';
  import difference from 'lodash/difference';
  import commonCoreStrings from 'kolibri.coreVue.mixins.commonCoreStrings';

  export default {
    name: 'UserTable',
    components: {
      CoreTable,
      UserTypeDisplay,
    },
    mixins: [commonCoreStrings],
    props: {
      users: {
        type: Array,
        required: true,
      },
      emptyMessage: {
        type: String,
      },
      selectable: {
        type: Boolean,
        default: false,
      },
      // TODO bring string into this component after stringfreeze
      selectAllLabel: {
        type: String,
      },
      // TODO bring string into this component after stringfreeze
      userCheckboxLabel: {
        type: String,
      },
      // used for optional checkboxes
      value: {
        type: Array,
        default: null,
      },
      isCoach: {
        type: Boolean,
        default: false,
      },
      infoDescriptor: {
        type: String,
        default: '',
      },
    },
    computed: {
      allAreSelected() {
        return Boolean(this.users.length) && this.users.every(user => this.value.includes(user.id));
      },
    },
    methods: {
      userIsSelected(id) {
        return this.value.includes(id);
      },
      selectAll(checked) {
        const currentUsers = this.users.map(user => user.id);
        if (checked) {
          return this.$emit('input', [...this.value, ...currentUsers]);
        }
        return this.$emit('input', difference(this.value, currentUsers));
      },
      selectUser(id, checked) {
        const selected = Array.from(this.value);
        if (checked) {
          selected.push(id);
          return this.$emit('input', selected);
        }
        return this.$emit('input', selected.filter(selectedId => selectedId !== id));
      },
    },
    $trs: {
      role: 'Role',
      userActionsColumnHeader: 'Actions',
    },
  };

</script>


<style lang="scss" scoped>

  .select-all {
    position: relative;
    // Overrides overflow-x: hidden rule for CoreTable th's
    overflow-x: visible;

    .k-checkbox-container {
      margin-right: -70px;
    }

    .k-checkbox-label {
      // Add extra padding to align label with table headers
      padding-top: 4px;
    }
  }

  .empty-message {
    margin-bottom: 16px;
  }

  .role-badge {
    display: inline-block;
    padding: 0;
    padding-right: 8px;
    padding-left: 8px;
    margin-left: 16px;
    font-size: small;
    white-space: nowrap;
    border-radius: 4px;
  }

  .overflow-label {
    position: absolute;
    top: 8px;
    white-space: nowrap;
  }

</style>
